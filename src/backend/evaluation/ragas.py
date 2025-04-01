
from typing import List, Dict
import os
import json
import csv
import logging
from datetime import datetime
from src.backend.utils.settings import SETTINGS
from src.backend.chat.service_container import ServiceContainer

# Import RAGAS components
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_relevancy,
    context_recall
)
from ragas.llms import OpenAI as RagasOpenAI
from datasets import Dataset

logger = logging.getLogger(__name__)


class RagasEvaluator:
    """RAGAS evaluator for your chatbot system."""
    
    def __init__(self, services: ServiceContainer = None):
        """Initialize the evaluator."""
        self.services = services
        self.ragas_llm = RagasOpenAI(api_key=SETTINGS.OPENAI_API_KEY)
        self.metrics = [
            faithfulness(llm=self.ragas_llm),
            answer_relevancy(llm=self.ragas_llm),
            context_relevancy(llm=self.ragas_llm),
            context_recall(llm=self.ragas_llm)
        ]

    async def extract_conversations_by_session(
        self, session_id: str, limit: int = 100
    ) -> List[Dict]:
        cursor = self.services.chat_history_collection.find(
            {"session_id": session_id}
        ).sort("timestamp", 1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def extract_conversations_by_customer(
        self, customer_id: str, limit: int = 100
    ) -> Dict[str, List[Dict]]:
        msg_cursor = self.services.chat_history_collection.find(
            {"customer_id": customer_id}
        ).sort("timestamp", 1).limit(limit)
        all_msg = await msg_cursor.to_list(length=limit)
        return all_msg

    def prepare_conversation_pairs(self, messages: List[Dict]) -> List[Dict]:
        conversation_pairs = []
        current_question = None

        for i, msg in messages:
            role = msg.get("role")
            content = msg.get("content")

            if role in ["USER", "user"]:
                current_question = content
            elif role in ["BOT"] and current_question and i > 0:
                metadata = msg.get("metadata", {})
                # This is a response to the current question
                conversation_pairs.append({
                    "question": current_question,
                    "answer": content,
                    "metadata": metadata,
                    "timestamp": msg.get("timestamp"),
                    "session_id": msg.get("session_id"),
                    "customer_id": msg.get("customer_id")
                })
                current_question = None
        return conversation_pairs
    
    def extract_context_from_metadata(self, conversation_pairs: List[Dict]) -> List[Dict]:
        for pair in conversation_pairs:
            contexts = []
            metadata = pair.get("metadata", {})
            
            # Extract contexts from various potential metadata fields
            if metadata.get("full_analysis", False):
                # If this includes sentiment analysis results
                contexts.append(f"Sentiment analysis: Score {metadata.get('sentiment_score', 'N/A')}, Confidence: {metadata.get('sentiment_confidence', 'N/A')}")
            
            # Look for course data or search results in your metadata
            if "courses_json" in metadata:
                contexts.append(metadata["courses_json"])
            
            if "search_results" in metadata:
                contexts.append(metadata["search_results"])
            
            # If no contexts could be extracted, use a placeholder
            if not contexts:
                contexts = ["No context metadata available"]
            
            pair["contexts"] = contexts
        
        return conversation_pairs

    def prepare_eval_dataset(self, conversation_pairs: List[Dict]) -> Dataset:
        data = {
            "question": [],
            "answer": [],
            "contexts": [],
            "session_id": [],
            "timestamp": []
        }
        for pair in conversation_pairs:
            data["question"].append(pair["question"])
            data["answer"].append(pair["answer"])
            data["contexts"].append(
                pair.get("contexts", ["No context available"])
            )
            data["session_id"].append(pair.get("session_id", ""))
            data["timestamp"].append(pair.get("timestamp", ""))
        
        return Dataset.from_dict(data)
    
    def evaluate(self, dataset: Dataset) -> Dict[str, float]:
        """Evaluate the dataset using RAGAS."""
        results = evaluate(
            dataset=dataset,
            metrics=self.metrics,
            llm=self.ragas_llm
        )
        # Convert to regular dictionary with float values
        return {metric: float(score) for metric, score in results.items()}
    
    async def single_session_eval(
        self, session_id: str, session_chat_limit: int
    ) -> Dict:
        messages = await self.extract_conversations_by_session(
            session_id, session_chat_limit
        )
        if not messages:
            return {
                "session_id": session_id,
                "error": "No messages found for this session",
                "metrics": {}
            }
        conversation_pairs = self.prepare_conversation_pairs(messages)
        conversation_pairs = self.extract_contexts_from_metadata(
            conversation_pairs
        )
        dataset = self.prepare_eval_dataset(conversation_pairs)
        metrics = self.evaluate(dataset)
        customer_id = messages[0].get("customer_id") if messages else None
        result = {
            "session_id": session_id,
            "customer_id": customer_id,
            "message_count": len(messages),
            "conversation_pairs": len(conversation_pairs),
            "metrics": metrics,
            "conversations": [
                {
                    "question": pair["question"],
                    "answer": pair["answer"],
                    "timestamp": pair.get("timestamp")
                }
                for pair in conversation_pairs
            ]
        }
        return result

    async def save_evaluation_results(
        self, results: Dict, base_dir: str = None
    ) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results["evaluation_timestamp"] = timestamp
        if not base_dir:
            base_dir = "evaluations/ragas_reports"
            os.makedirs(base_dir, exist_ok=True)
        
        if "session_id" in results:
            folder_name = f"session_{results['session_id']}_{timestamp}"
        else:
            folder_name = f"evaluation_{timestamp}"

        eval_folder = os.path.join(base_dir, folder_name)
        os.makedirs(eval_folder, exist_ok=True)

        json_filepath = os.path.join(eval_folder, "results.json")
        with open(json_filepath, "w") as f:
            json.dump(results, f, indent=2, default=str)
        csv_filepath = os.path.join(eval_folder, "metrics.csv")
        
        # Extract data for CSV
        # First, for metrics
        metrics_data = []
        if "metrics" in results:
            # For single evaluation (session or customer)
            for metric, score in results["metrics"].items():
                metrics_data.append({
                    "id": results.get("session_id", "unknown"),
                    "metric": metric,
                    "score": score,
                    "timestamp": timestamp
                })

        # Write metrics to CSV
        if metrics_data:
            with open(csv_filepath, 'w', newline='') as f:
                fieldnames = ["id", "metric", "score", "timestamp"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in metrics_data:
                    writer.writerow(row)
            
        # Save conversations CSV if available
        if "conversations" in results and results["conversations"]:
            conversations_csv_filepath = os.path.join(eval_folder, "conversations.csv")
            with open(conversations_csv_filepath, 'w', newline='', encoding='utf-8') as f:
                fieldnames = ["id", "question", "answer", "timestamp"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for i, convo in enumerate(results["conversations"]):
                    writer.writerow({
                        "id": i + 1,
                        "question": convo.get("question", ""),
                        "answer": convo.get("answer", ""),
                        "timestamp": convo.get("timestamp", "")
                    })
        
        logger.info(f"Evaluation results saved to: {eval_folder}")
        return eval_folder