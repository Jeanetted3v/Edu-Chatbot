import logging
from typing import Tuple, Optional
from pydantic import BaseModel
from pydantic_ai import Agent
from src.backend.models.human_agent import (
    AgentDecision,
    ToggleReason,
    AgentType,
    MessageRole
)
from src.backend.utils.llm_model_factory import LLMModelFactory

logger = logging.getLogger(__name__)


class QueryHandlerResponse(BaseModel):
    """Response model for query handler"""
    response: str
    intent: str
    english_level: Optional[str]
    course_interest: Optional[str]
    lexile_level: Optional[str]


class QueryHandler:
    def __init__(self, services):
        """Initialize QueryHandler with all class instances from services"""
        self.services = services
        self.cfg = services.cfg
        self.mongo_client = services.mongodb_client.client
        model_config = dict(self.cfg.query_handler.llm)
        model = LLMModelFactory.create_model(model_config)
        logger.info(f"LLM model instance created: {model}")
        self.agent = Agent(
            model=model,
            result_type=QueryHandlerResponse,
            system_prompt=self.cfg.query_handler_prompts['sys_prompt'],
        )
    
    async def analyze_sentiment(
        self, session_id: str, customer_id: str, message: str, total_count: int
    ) -> Tuple[dict, AgentDecision]:
        session = self.services.active_sessions.get(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found")
            return None, AgentDecision(
                should_transfer=False,
                response="Session not found. Please try again.",
                transfer_reason=None
            )
        # Get chat history for stats
        chat_history = await self.services.get_chat_history(
            session_id, customer_id)

        # If already with human agent, continue there
        if session.current_agent == AgentType.HUMAN:
            await chat_history.add_turn('user', message)  # Add message without analysis
            return {}, AgentDecision(
                should_transfer=True,
                response=None,  # Let human agent UI handle response
                transfer_reason=None
            )
        recent_turns = await chat_history.get_recent_turns()
        last_analyzed = sum(1 for turn in recent_turns if turn.get(
            'full_analysis', False)
        )

        # Default values if we skip analysis
        analysis_result = None
        agent_decision = AgentDecision(
            should_transfer=False,
            response=None,
            transfer_reason=None
        )
        if total_count < self.cfg.msg_analyzer.min_message_length:
            logger.info("Not enough messages for sentiment analysis")
            return analysis_result, agent_decision
        elif not self.services.message_analyzer:
            logger.info("Message analyzer is None, skipping sentiment analysis")
            analysis_result = None
            return analysis_result, agent_decision
        else:
            analysis_result = await self.services.message_analyzer.analyze(
                message,
                total_count,
                last_analyzed
            )
            logger.info(f"Analysis result: {analysis_result}")
        # Check if human agent is needed
        recent_history = await chat_history.format_history_for_prompt()
        needs_human = await self.services.human_handler._detect_human_request(
            message, recent_history
        )
        logger.info(f"Needs human agent: {needs_human}")
        
        # Determine if we should transfer
        should_transfer = (
            needs_human or
            (
                analysis_result.score <
                self.services.human_handler.cfg.human_agent.sentiment_threshold and
                analysis_result.confidence >
                self.services.human_handler.cfg.human_agent.confidence_threshold
            )
        )
        
        # Handle transfer if needed
        if should_transfer:
            transfer_reason = (
                ToggleReason.CUSTOMER_REQUEST if needs_human
                else ToggleReason.SENTIMENT_BASED
            )
            # Return decision, let the caller handle the transfer
            return analysis_result, AgentDecision(
                should_transfer=True,
                response="Transferring to human agent...",
                transfer_reason=transfer_reason
            )
        
        return analysis_result, agent_decision

    async def handle_query(
        self, query: str, session_id: str, customer_id: str
    ) -> tuple[str, dict, str]:
        """Main entry point for handling user queries."""
        try:
            session = await self.services.get_or_create_session(
                session_id, customer_id
            )
            chat_history = await self.services.get_chat_history(
                session_id, customer_id)

            if session.current_agent == AgentType.HUMAN:
                # Add message to chat history without any sentiment analysis
                await chat_history.add_turn(MessageRole.USER, query)
                logger.info(f"Message from customer forwarded to human agent "
                            f"for session {session_id}")
                return "Message forwarded to human agent"

            # For bot processing:
            # Step 1: Analyze sentiment and check if should transfer to human
            total_count = await chat_history.collection.count_documents(
                {"session_id": session_id})
            logger.info(f"Current session message count: {total_count}")
            analysis_result, agent_decision = await self.analyze_sentiment(   # need to handle is msg analyzer is None
                session_id, customer_id, query, total_count)
            
            # Add message to chat history with metadata from analysis
            if analysis_result:
                metadata = {
                    'sentiment_score': analysis_result.score,
                    'sentiment_confidence': analysis_result.confidence,
                    'full_analysis': analysis_result.full_analysis
                }
                await chat_history.add_turn(
                    MessageRole.USER, query, metadata=metadata
                )
            else:
                await chat_history.add_turn(MessageRole.USER, query)
            logger.info(f"Analysis result: {analysis_result}")
            logger.info(f"AgentDecision if transfer to human: {agent_decision}")
            
            if agent_decision.should_transfer:
                success = await self.services.human_handler.transfer_to_human(
                    session_id,
                    agent_decision.transfer_reason
                )
                logger.info(f"Transfer to human agent: {success}")
                if success:
                    if agent_decision.response:
                        await chat_history.add_turn(
                            MessageRole.SYSTEM, agent_decision.response
                        )
                    return "Message forwarded to human agent"
                else:
                    transfer_failed_msg = (
                        "All our staff are currently busy. "
                        "I'll continue to assist you."
                    )
                    await chat_history.add_turn(
                        MessageRole.SYSTEM, transfer_failed_msg
                    )
                    return transfer_failed_msg

            msg_history = await chat_history.format_history_for_prompt()

            # add reasoning LLM 
            # retrieve search results
            search_results = await self.services.hybrid_retriever.search(query)
            formatted_search_results, top_result = (
                self.services.hybrid_retriever.format_search_results(
                    search_results
                )
            )
            result = await self.agent.run(
                self.cfg.query_handler_prompts['user_prompt'].format(
                    query=query,
                    message_history=msg_history,
                    search_results=top_result
                )
            )
            response = result.data.response
            intent = result.data.intent
            logger.info(f"Intent: {intent}, Top Search Result: {top_result}"
                        f", Response: {response}")
            await chat_history.add_turn(
                MessageRole.BOT,
                response,
                metadata={
                    'intent': intent,
                    'top_search_result': top_result
                }
            )
            return response, intent, top_result
                
        except Exception as e:
            logger.error(f"Error handling query: {e}")
            error_msg = (
                "Sorry, there was an error processing your query. "
                "Please try again later or contact our support."
            )
            await chat_history.add_turn(MessageRole.BOT, error_msg)
            return error_msg