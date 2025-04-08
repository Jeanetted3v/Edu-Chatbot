"""Utility class for DeepEval test preparation."""

import os
import json, csv
import logging
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

from deepeval.dataset import EvaluationDataset
from deepeval.test_case import ConversationalTestCase, LLMTestCase

logger = logging.getLogger(__name__)


class EvalUtils:
    """Utility class for preparing DeepEval test cases from MongoDB data."""
    
    def __init__(self, chat_history_collection=None):
        """Initialize the utility class."""
        self.chat_history_collection = chat_history_collection

    async def extract_conversations_by_session(self, session_id: str, limit: int = 100) -> List[Dict]:
        """Extract conversation history for a specific session.
        
        Args:
            session_id: The unique session identifier
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of message dictionaries sorted by timestamp
        """
        if self.chat_history_collection is None:
            await self.connect()
            
        cursor = self.chat_history_collection.find(
            {"session_id": session_id}
        ).sort("timestamp", 1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def extract_conversations_by_customer(
        self, customer_id: str, limit: int = 100
    ) -> Dict[str, List[Dict]]:
        msg_cursor = self.chat_history_collection.find(
            {"customer_id": customer_id}
        ).sort("timestamp", 1).limit(limit)
        all_msg = await msg_cursor.to_list(length=limit)
        return all_msg

    def prepare_test_case_deepeval(
        self, messages: List[Dict], chatbot_role: str, session_id: str
    ) -> ConversationalTestCase:
        """Convert messages to DeepEval ConversationalTestCase format.
        
        Args:
            messages: List of message dictionaries from MongoDB
            chatbot_role: Description of the chatbot's role
            session_id: Session ID for identification
            
        Returns:
            ConversationalTestCase object for DeepEval evaluation
        """
        messages.sort(key=lambda x: x.get("timestamp", 0))

        turns = []
        current_input = None
        
        for msg in messages:
            role = msg.get("role", "").lower()
            content = msg.get("content", "")
            if role == "user":
                current_input = content
            elif role == "bot" and current_input is not None:
                turn = LLMTestCase(
                    input=current_input,
                    actual_output=content
                )
                turns.append(turn)
                current_input = None

        test_case = ConversationalTestCase(
            chatbot_role=chatbot_role,
            turns=turns
        )
        test_case.id = session_id
        logger.info(f"Created test case for session {session_id} "
                    f"with {len(turns)} turns")
        return test_case
    
    async def create_dataset_deepeval(
        self,
        session_ids: List[str],
        chatbot_role: str,
        session_chat_limit: int
    ) -> EvaluationDataset:
        """Create an EvaluationDataset from multiple chat sessions.
        
        Args:
            session_ids: List of session IDs to include
            chatbot_role: Description of the chatbot's role
            session_chat_limit: Maximum number of messages per session
            
        Returns:
            EvaluationDataset with test cases for each session
        """
        test_cases = []
        try:
            for session_id in session_ids:
                try:
                    messages = await self.extract_conversations_by_session(
                        session_id, limit=session_chat_limit
                    )
                    test_case = self.prepare_test_case_deepeval(
                        messages, chatbot_role, session_id
                    )
                    test_cases.append(test_case)
                except Exception as e:
                    logger.error(f"Error creating test case for session "
                                 f"{session_id}: {e}")
        except Exception as e:
            logger.error(f"Error creating dataset: {e}")
            raise
        logger.info(f"Created dataset with {len(test_cases)} test cases")
        return EvaluationDataset(test_cases=test_cases)
    
    @staticmethod
    async def save_results_deepeval(
        metrics_results: List[Tuple[str, float, str, bool]],
        base_dir: str,
        test_case: Optional[Any] = None
    ) -> dict:
        """Save evaluation results to a CSV and a JSON file.
        
        Args:
            result: Result object from assert_test
            base_dir: Base directory for saving results
            
        Returns:
            Path to the saved file
        """
        os.makedirs(base_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = getattr(test_case, "id", "unknown_session")
        filename = f"deepeval_{session_id}_{timestamp}.json"
        json_filepath = os.path.join(base_dir, filename)
        csv_filename = f"deepeval_{session_id}_{timestamp}.csv"
        csv_filepath = os.path.join(base_dir, csv_filename)

        result_data = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "metrics": {}
        }
        for metric_name, score, reason, passed in metrics_results:
            result_data["metrics"][metric_name] = {
                "score": score,
                "passed": passed,
                "reason": reason
            }
    
        with open(csv_filepath, 'w', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(['Session ID', 'Timestamp', 'Metric', 'Score', 'Passed', 'Reason'])
        
            # Write rows for each metric
            for metric_name, score, reason, passed in metrics_results:
                csv_writer.writerow([
                    session_id,
                    datetime.now().isoformat(),
                    metric_name,
                    score,
                    'PASSED' if passed else 'FAILED',
                    reason[:500]  # Limit reason length for CSV readability
                ])
        with open(json_filepath, 'w') as json_file:
            json.dump(result_data, json_file, indent=4)
        
        return {
            "json_path": json_filepath,
            "csv_path": csv_filepath
        }