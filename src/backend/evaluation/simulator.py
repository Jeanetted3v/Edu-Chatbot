"""To run:
python -m src.backend.evaluation.simulator
"""
import logging
import logfire
import asyncio
import uuid
import hydra
import traceback

from omegaconf import DictConfig
from pydantic_ai import Agent
from src.backend.utils.logging import setup_logging
from src.backend.chat.service_container import ServiceContainer
from src.backend.utils.llm_model_factory import LLMModelFactory


logger = logging.getLogger(__name__)
logger.info("Setting up logging configuration.")
setup_logging()
logfire.configure(send_to_logfire='if-token-present')


class Simulator:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.services = ServiceContainer(cfg)
        self.session_id = f"session_{uuid.uuid4()}"
        self.customer_id = f"customer_{uuid.uuid4()}"
        self.agent_mode = "bot"
        model_config = dict(self.cfg.simulator.llm)
        model = LLMModelFactory.create_model(model_config)
        logger.info(f"LLM model instance created: {model}")
        self.prompts = cfg.simulator_prompts
        self.simulator_agent = Agent(
            model=model,
            result_type=str,
            system_prompt=self.prompts['sys_prompt'],
        )
        self.simulation_mode = cfg.simulator.enabled
    
    async def initialize(self):
        """Async initialization method"""
        await self.services.initialize()
        await self.services.get_or_create_session(
            self.session_id, self.customer_id
        )
        logger.info(f"Session created with ID: {self.session_id}, "
                    f"Customer ID: {self.customer_id}")

    def print_conversation(self, role: str, content: str) -> None:
        """Print conversation with appropriate role labels"""
        if role == 'user':
            print(f"\nSimulated User: {content}")
        else:
            print(f"\n{role.capitalize()}: {content}")

    async def run_simulated_session(self, num_exchanges: int) -> None:
        """Run a simulated session with the chatbot"""
        chat_history = await self.services.get_chat_history(
            self.session_id,
            self.customer_id
        )
        recent_turns = await chat_history.get_recent_turns(1)

        if not recent_turns:
            first_query = "Hi, I'm a parent, would like to make an inquiry"
            self.print_conversation("user", first_query)
            await chat_history.add_turn('user', first_query)
            bot_response = await self.services.query_handler.handle_query(
                first_query,
                self.session_id,
                self.customer_id
            )
            self.print_conversation("assistant", bot_response)
        else:
            # Get the last bot response from history
            last_turn = recent_turns[0]
            bot_response = last_turn["content"] if last_turn["role"] == "assistant" else ""
        
        for i in range(num_exchanges):
            print(f"\nExchange {i+1}/{num_exchanges}")
            simulated_query = await self.get_simulated_user_query(bot_response)
            self.print_conversation("user", simulated_query)
            await chat_history.add_turn('user', simulated_query)
            bot_response = await self.services.query_handler.handle_query(
                simulated_query,
                self.session_id,
                self.customer_id
            )
            self.print_conversation("assistant", bot_response)
            await asyncio.sleep(1)
        print("Simulated session completed.")
        
    async def get_simulated_user_query(self, last_bot_response: str) -> str:
        """Get next query from LLM simulator"""
        chat_history = await self.services.get_chat_history(
            self.session_id,
            self.customer_id
        )
        # Format history for the simulator
        history_str = await chat_history.format_history_for_prompt()
        logger.info(f"Chat history for simulation: {history_str}")

        try:
            next_user_query = await self.simulator_agent.run(
                self.prompts['user_prompt'].format(
                    last_bot_response=last_bot_response,
                    msg_history=history_str
                )
            )
            next_user_query = next_user_query.data
            return next_user_query
        except Exception as e:
            logger.error(f"Error generating simulated query: {e}")
            return "Could you explain that again? I didn't understand."
    
    async def process_query(self, query: str) -> str:
        """Process user query"""
        self.print_conversation("user", query)
        chat_history = await self.services.get_chat_history(
            self.session_id,
            self.customer_id
        )
        await chat_history.add_turn('user', query)
        response = await self.services.query_handler.handle_query(
            query,
            self.session_id,
            self.customer_id
        )
        self.print_conversation("assistant", response)
        return response

    async def run(self) -> None:
        """Run the CLI tester"""
        try:
            await self.initialize()
            print("\nWelcome to the Edu Chatbot Tester!")
            print("Commands:")
            print("- 'quit' or 'exit': End session")
            last_bot_response = ""
            while True:
                try:
                    if self.simulation_mode:
                        query = await self.get_simulated_user_query(
                            last_bot_response)
                        # Check for simulation termination signals
                        if any(word in query.lower() for word in ["goodbye", "bye", "exit", "quit"]):
                            print("\nSimulation ended by LLM.")
                            self.simulation_mode = False
                            continue
                    else:
                        query = input("\nUser: ").strip()

                    if query.lower() in ['quit', 'exit']:
                        print("\nGoodbye!")
                        break
                    elif query.lower() == 'simulate':
                        self.simulation_mode = not self.simulation_mode
                        mode_str = "enabled" if self.simulation_mode else "disabled"
                        print(f"\nLLM simulation mode {mode_str}")
                        continue
                    elif query.lower().startswith('auto'):
                        # Parse number of exchanges
                        parts = query.lower().split()
                        num_exchanges = 5  # Default
                        if len(parts) > 1 and parts[1].isdigit():
                            num_exchanges = int(parts[1])
                        
                        await self.run_simulated_session(num_exchanges)
                        continue
                    elif not query:
                        continue
                    last_bot_response = await self.process_query(query)

                except KeyboardInterrupt:
                    print("\nGoodbye!")
                    break
                except Exception as e:
                    logging.error(f"Error processing query: {e}")
                    print(f"\nError: {e}")
                    traceback.print_exc()
        finally:
            await self.services.cleanup()
                

@hydra.main(
    version_base=None,
    config_path="../../../config",
    config_name="config")
def main(cfg) -> None:
    
    async def async_main():
        simulator = Simulator(cfg)
        await simulator.run()
    
    asyncio.run(async_main())


if __name__ == "__main__":
    main()