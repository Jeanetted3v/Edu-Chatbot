import os
import glob
import yaml
import json
import shutil
import logging
from datetime import datetime
from omegaconf import DictConfig
from typing import List, Tuple, Dict
from pydantic import BaseModel
from pydantic_ai import Agent
from src.backend.utils.llm_model_factory import LLMModelFactory
from src.backend.evaluation.simulator_no_db import ChatBotSimulator

logger = logging.getLogger(__name__)


class Summary(BaseModel):
    title: str
    summary: str


class InputDocAgentResult(BaseModel):
    summary: List[Summary]


class PromptCreatorResult(BaseModel):
    chatbot_system_prompt: str
    simulator_system_prompt: str


class PromptOptimizerResult(BaseModel):
    new_chatbot_prompt: str
    new_simulator_prompt: str
    score: float  # score of the old prompts
    feedback: str  # feedback on the old prompts
    optimize: bool  # whether to regenerate prompts


class ChatbotCreator():
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        input_doc_agent_model_config = dict(self.cfg.input_doc_agent)
        self.simulator = ChatBotSimulator(self.cfg)
        self.input_doc_agent_model = LLMModelFactory.create_model(input_doc_agent_model_config)
        self.input_doc_agent = Agent(
            model=self.input_doc_agent_model,
            result_type=InputDocAgentResult,
            system_prompt=self.cfg.input_doc_agent_prompts['system_prompt'],
        )
        prompt_creator_model_config = dict(self.cfg.prompt_creator)
        self.prompt_creator_model = LLMModelFactory.create_model(prompt_creator_model_config)
        self.prompt_creator_agent = Agent(
            model=self.prompt_creator_model,
            result_type=PromptCreatorResult,
            system_prompt=self.cfg.prompt_creator_prompts['system_prompt'],
        )
        prompt_validator_model_config = dict(self.cfg.prompt_validator)
        self.prompt_validator_model = LLMModelFactory.create_model(prompt_validator_model_config)
        self.prompt_validator_agent = Agent(
            model=self.prompt_validator_model,
            result_type=Tuple[str, str],
            system_prompt=self.cfg.prompt_validator_prompts['system_prompt'],
        )
        prompt_optimizer_model_config = dict(self.cfg.prompt_optimizer)
        self.prompt_optimizer_model = LLMModelFactory.create_model(prompt_optimizer_model_config)
        self.prompt_optimizer_agent = Agent(
            model=self.prompt_optimizer_model,
            result_type=PromptOptimizerResult,
            system_prompt=self.cfg.prompt_optimizer_prompts['system_prompt'],
        )

    async def summarize_input_doc(self) -> str:
        """Summarize the input document using the input_doc_agent."""
        input_doc = self.simulator.prepare_rag_context()

        formatted_input_doc = self.cfg.input_doc_agent_prompts['user_prompt'].format(input_doc=input_doc)
        result = await self.input_doc_agent.run(prompt=formatted_input_doc)
        parsed = InputDocAgentResult.model_validate(result.data)
        summary_dict = parsed.model_dump()
        summary_str = json.dumps(summary_dict, indent=2, ensure_ascii=False)
        return summary_str
    
    async def create_prompt(self, input_doc_summary: str) -> Tuple[str, str]:
        """Create a prompt using the prompt_creator_agent."""
        formatted_prompt = self.cfg.prompt_creator_prompts['user_prompt'].format(
            input_doc_summary=input_doc_summary
        )
        prompts = await self.prompt_creator_agent.run(
            prompt=formatted_prompt,
        )
        simulator_prompt = prompts.data.simulator_system_prompt
        chatbot_prompt = prompts.data.chatbot_system_prompt
        simulator_prompt, chatbot_prompt = await self.validate_prompt(
            simulator_prompt=simulator_prompt,
            chatbot_prompt=chatbot_prompt
        )
        # update working prompt files
        self.update_prompt_files(simulator_prompt, chatbot_prompt)
        return simulator_prompt, chatbot_prompt
    
    async def validate_prompt(
        self, simulator_prompt: str, chatbot_prompt: str
    ) -> Tuple[str, str]:
        """Check the prompts using the prompt_checker_agent."""
        formatted_prompt = self.cfg.prompt_validator_prompts['user_prompt'].format(
            simulator_prompt=simulator_prompt,
            chatbot_prompt=chatbot_prompt
        )
        prompts = await self.prompt_validator.run(
            prompt=formatted_prompt,
        )
        new_chatbot_system_prompt = prompts.data.new_chatbot_system_prompt
        new_simulator_system_prompt = prompts.data.new_simulator_system_prompt
        return new_chatbot_system_prompt, new_simulator_system_prompt
    
    def update_prompt_files(
        self, simulator_prompt: str, chatbot_prompt: str
    ) -> None:
        """Update prompt file with the latest prompts."""
        sim_path = self.cfg.simulator_prompts_filepath
        chat_path = self.cfg.chatbot_prompts_filepath
        
        # Update prompts in simulator prompt file
        with open(sim_path, "r") as f:
            sim_data = yaml.safe_load(f)
        if "simulator_prompts" not in sim_data:
            sim_data["simulator_prompts"] = {}
        sim_data["simulator_prompts"]["system_prompt"] = simulator_prompt
        with open(sim_path, "w") as f:
            yaml.dump(sim_data, f)

        # Update prompts in query_handler pronmpt file
        with open(chat_path, "r") as f:
            chat_data = yaml.safe_load(f)
        chat_data["query_handler_prompts"]["response_agent"]["sys_prompt"] = chatbot_prompt
        with open(chat_path, "w") as f:
            yaml.dump(chat_data, f)

        logger.info("📝 Updated simulator and chatbot prompt files.")

    def save_audit_log(
        self,
        session_id: str,
        iteration: int,
        new_simulator_prompt: str,
        new_chatbot_prompt: str,
        old_simulator_prompt: str,
        old_chatbot_prompt: str,
        score: float,
        feedback: str,
        conversation: List[Dict],
        output_dir: str = "data/audit_logs"
    ) -> None:
        """Save prompts, score, feedback, and conversation."""
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        audit_record = {
            "session_id": session_id,
            "iteration": iteration,
            "timestamp": timestamp,
            "new_simulator_prompt": new_simulator_prompt,
            "new_chatbot_prompt": new_chatbot_prompt,
            "old_simulator_prompt": old_simulator_prompt,
            "old_chatbot_prompt": old_chatbot_prompt,
            "score": score,
            "feedback": feedback,
            "conversation": conversation,
            
        }

        file_path = os.path.join(output_dir, f"{session_id}_{timestamp}.json")
        with open(file_path, "w") as f:
            json.dump(audit_record, f, indent=2, ensure_ascii=False)

        logger.info(f"📦 Audit log saved to {file_path}")

    async def optimize_prompt(self) -> str:
        """Optimize prompts using the prompt_checker_agent in a loop.
        Regenerates prompts until regenerate_prompts is False.
        Deletes previous simulation JSONs before each new simulation run.
        """
        simulation_dir = self.cfg.simulation_dir
        optimize = True
        iteration = 1

        while optimize:
            logger.info(f"Optimizing prompts, iteration {iteration}")

            # Clear the simulation directory before each run
            shutil.rmtree(simulation_dir, ignore_errors=True)
            os.makedirs(simulation_dir, exist_ok=True)
            # Run the simulation with the current prompts
            await self.simulator.run_simulations(self.cfg.num_simulations)
            old_simulator_prompt = self.cfg.simulator_prompts['system_prompt']
            old_chatbot_prompt = self.cfg.query_handler_prompts['response_agent']['sys_prompt']
            
            json_files = glob.glob(os.path.join(self.cfg.simulation_dir, '*.json'))
            turns = self.simulator.extract_customer_bot(json_files)
            # Format the conversation text for the checker prompt
            conversation_examples = []
            for i, turn in enumerate(turns, 1):
                conversation_examples.append(f"Example {i}\nUser: {turn['customer_inquiry']}\nBot: {turn['bot_response']}")
            conversation_block = "\n\n".join(conversation_examples)

            formatted_prompt = self.cfg.prompt_optimizer_prompts['user_prompt'].format(
                simulator_prompt=old_simulator_prompt,
                chatbot_prompt=old_chatbot_prompt,
                conversation=conversation_block
            )
            result = await self.prompt_optimizer_agent.run(
                prompt=formatted_prompt,
            )
            chatbot_prompt = result.data.new_chatbot_prompt
            simulator_prompt = result.data.new_simulator_prompt
            score = result.data.score
            optimize = result.data.optimize
            feedback = result.data.feedback

            # double check the new prompts to make sure they are valid
            chatbot_prompt, simulator_prompt = await self.validate_prompt(
                simulator_prompt=simulator_prompt,
                chatbot_prompt=chatbot_prompt
            )
            # Save the audit log
            session_id = f"session_iter_{iteration}"
            self.save_audit_log(
                session_id=session_id,
                new_simulator_prompt=simulator_prompt,
                new_chatbot_prompt=chatbot_prompt,
                old_simulator_prompt=old_simulator_prompt,
                old_chatbot_prompt=old_chatbot_prompt,
                score=score,
                feedback=feedback,
                conversation=turns,
                output_dir="data/audit_logs"
            )
            
            # update working prompt files each time
            self.update_prompt_files(simulator_prompt, chatbot_prompt)

            logger.info(f"✅ Iteration {iteration} complete — Score: {score:.2f}")
            logger.info(f"📝 Feedback: {feedback}")

            if optimize:
                logger.info("🔄 Regenerating prompts...")
            iteration += 1

        logger.info("🎯 Final prompts generated.")
        return chatbot_prompt

    async def chatbot_creation(self) -> None:
        """Main entry point to create a chatbot."""
        logging.info("Creating chatbot...")
        summary = await self.summarize_input_doc()
        simulator_prompt, chatbot_prompt = await self.create_prompt(summary)
        chatbot_prompt = await self.optimize_prompt(simulator_prompt, chatbot_prompt)
        logger.info(f"🤖 Chatbot created with the following prompt: {chatbot_prompt}")
        return None

