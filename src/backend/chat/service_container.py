from datetime import datetime
import logging
from src.backend.database.mongodb_client import MongoDBClient
from src.backend.chat.intent_classifier import IntentClassifier
from src.backend.chat.hybrid_retriever import HybridRetriever
from src.backend.chat.course_service import CourseService
from src.backend.chat.sentiment_analyzer import SentimentAnalyzer
from src.backend.chat.msg_analyzer import MessageAnalyzer
from src.backend.chat.human_agent_handler import HumanAgentHandler
from src.backend.chat.query_handler import QueryHandler
from src.backend.chat.chat_history import ChatHistory
from src.backend.models.human_agent import AgentType, ChatSession
from src.backend.utils.settings import SETTINGS


logger = logging.getLogger(__name__)


class ServiceContainer:
    """Container for all service instances with centralized initialization."""
    
    def __init__(self, cfg):
        self.cfg = cfg
        self.mongodb_client = None
        self.intent_classifier = None
        self.hybrid_retriever = None
        self.course_service = None
        self.sentiment_analyzer = None
        self.message_analyzer = None
        self.human_handler = None
        self.query_handler = None
        self.chat_histories = {}
        self.active_sessions = {}
        
    async def initialize(self):
        """Initialize all service components with proper dependency order."""
        try:
            self.mongodb_client = MongoDBClient(SETTINGS.MONGODB_URI)
            await self.mongodb_client.connect()
            self.intent_classifier = IntentClassifier(self.cfg)
            self.hybrid_retriever = HybridRetriever(self.cfg)
            self.course_service = CourseService(self)
            self.sentiment_analyzer = SentimentAnalyzer(self.cfg)
            self.message_analyzer = MessageAnalyzer(self)
            self.human_handler = HumanAgentHandler(self)
            self.query_handler = QueryHandler(self)
        except Exception as e:
            logger.error(f"Error initializing services: {e}")
            raise
    
    async def get_chat_history(self, session_id: str, customer_id: str):
        """Get or create chat history for a session."""
        if session_id not in self.chat_histories:
            logger.info(f"Creating new chat history for {session_id}")
            self.chat_histories[session_id] = ChatHistory(
                self.mongodb_client.client,
                session_id,
                customer_id
            )
        return self.chat_histories[session_id]
    
    async def get_or_create_session(self, session_id: str, customer_id: str):
        """Get existing session or create a new one"""
        if session_id not in self.active_sessions:
            session = ChatSession(
                session_id=session_id,
                customer_id=customer_id,
                current_agent=AgentType.BOT,
                start_time=datetime.now(),
                last_interaction=datetime.now()
            )
            self.active_sessions[session_id] = session
            session.last_interaction = datetime.now()
            return session
    
        return self.active_sessions[session_id]
    
    async def cleanup(self):
        """Cleanup all resources."""
        if self.mongodb_client:
            await self.mongodb_client.cleanup()
        # Clear dictionaries
        self.active_sessions.clear()
        self.chat_histories.clear()
        logger.info("Cleanup complete")

    # TODO: Implement the following optuional methods:
    # def get_sessions_needing_help(self):
    #     """Get list of sessions that need human help"""
    #     from models import AgentType
        
    #     return [
    #         session_id for session_id, session in self.active_sessions.items()
    #         if getattr(session, 'needs_human_help', False) and 
    #            session.current_agent == AgentType.BOT
    #     ]
    
    # def mark_session_needs_help(self, session_id, needs_help=True):
    #     """Mark a session as needing human help"""
    #     if session_id in self.active_sessions:
    #         session = self.active_sessions[session_id]
    #         session.needs_human_help = needs_help