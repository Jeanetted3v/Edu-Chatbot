"""To run:
deepeval test run src/backend/evaluation/test_deepeval.py -v
Parallelization (e.g. n=4): -n 4
Use Cache with: -c
Verbose mode: -v
"""
import os
import json, csv
import pandas as pd
import logging
from omegaconf import DictConfig
from typing import Dict, List, Tuple
from datetime import datetime
from pydantic import BaseModel
from pydantic_ai import Agent
from hydra import initialize, compose
from omegaconf import DictConfig
import pytest
import asyncio
from src.backend.utils.logging import setup_logging
from src.backend.utils.settings import SETTINGS
from src.backend.database.mongodb_client import MongoDBClient
from deepeval.dataset import EvaluationDataset
from deepeval.test_case import ConversationalTestCase, LLMTestCase
from src.backend.dataloaders.local_doc_loader import (
    load_local_doc,
    LoadedUnstructuredDocument,
    LoadedStructuredDocument
)
from deepeval.test_case import LLMTestCaseParams
# conversational metrics
from deepeval.metrics import (
    ConversationalGEval,
    ConversationCompletenessMetric,
    ConversationRelevancyMetric,
    KnowledgeRetentionMetric,
    RoleAdherenceMetric
)
# non-conversational metrics
# from deepeval.metrics import (
#     AnswerRelevancy,
#     Faithfulness,
#     ContextualRelevancy,
#     ContextualPrecision,
#     ContextualRecall
# )


logger = logging.getLogger(__name__)
logger.info("Setting up logging configuration.")
setup_logging()
initialize(version_base=None, config_path="../../../config")
cfg = compose(config_name="eval")


class LLMGroundTruth(BaseModel):
    customer_inquiry: str
    llm_gt: str


class AllLLMGroundTruth(BaseModel):
    all_llmgt: List[LLMGroundTruth]


class DeepEval:
    """Utility class for preparing DeepEval test cases from MongoDB data."""
    
    def __init__(self, chat_history_collection=None):
        """Initialize the utility class."""
        self.chat_history_collection = chat_history_collection

    async def extract_conversations_by_session(
        self, session_id: str, limit: int = 100
    ) -> List[Dict]:
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

    async def extract_convo_to_df(
        self,
        session_ids: List[str],
        session_chat_limit: int = 100
    ) -> List[str]:
        all_rows = []
        for session_id in session_ids:
            try:
                messages = await self.extract_conversations_by_session(
                    session_id, limit=session_chat_limit
                )
                messages.sort(key=lambda x: x.get("timestamp", 0))
                i = 0
                while i < len(messages) - 1:
                    current_msg = messages[i]
                    next_msg = messages[i + 1]
                    if (current_msg['role'] == 'user' and
                            next_msg['role'] == 'bot'):
                        retrieval_context = ""
                        if "metadata" in next_msg:
                            metadata = next_msg["metadata"]
                            if metadata:
                                retrieval_context = metadata.get("top_search_result", "")
                        row = {
                            'session_id': session_id,
                            'customer_inquiry': current_msg.get("content", ""),
                            'bot_response': next_msg.get("content", ""),
                            'retrieval_context': retrieval_context,
                            'context': "",
                            'expected_output': ""
                        }
                        all_rows.append(row)
                        i += 2  # skip to the next pair
                    else:
                        i += 1
            except Exception as e:
                logger.error(f"Error exporting conversations to CSV: {e}")
                raise
        return pd.DataFrame(all_rows)
    
    async def fill_gt_llm(
        self,
        csv_dir: str,
        df: pd.DataFrame,
        system_prompt: str,
        user_prompt: str
    ) -> pd.DataFrame:
        documents = load_local_doc(cfg)
        rag_context = ""
        for doc in documents:
            if isinstance(doc, LoadedUnstructuredDocument):
                rag_context += f"\n\n{doc.content}"
            elif isinstance(doc, LoadedStructuredDocument):
                df_str = doc.content.to_string(index=False)
                rag_context += f"\n\n{df_str}"

        inquiries = df["customer_inquiry"].tolist()

        agent = Agent(
            "openai:gpt-4o-mini",
            result_type=AllLLMGroundTruth,
            system_prompt=system_prompt
        )
        formatted_inquiries = "\n".join([f"Inquiry {i+1}: {inq}" 
                                        for i, inq in enumerate(inquiries)])
        result = await agent.run(user_prompt.format(
            customer_inquiry=formatted_inquiries,
            context=rag_context,
            )
        )
        all_llmgt = result.data.all_llmgt
        for i, item in enumerate(all_llmgt):
            if i < len(df):
                df.at[i, "expected_output"] = item.llm_gt
        csv_file_path = os.path.join(csv_dir, 'conversations.csv')
        df.to_csv(csv_file_path, index=False)
        logger.info(f"CSV file saved at: {csv_file_path}")
        return csv_file_path, df
    
    async def load_datasets_from_df(
        self, df: pd.DataFrame, chatbot_role: str
    ) -> EvaluationDataset:
        """Load CSV and convert to multiple DeepEval ConversationalTestCases.
        
        Groups conversations by session_id.
        """
        datasets = []
        for session_id, session_df in df.groupby('session_id'):
            llm_test_cases = [
                LLMTestCase(
                    input=row['customer_inquiry'], 
                    actual_output=row['bot_response'],
                    retrieval_context=row['retrieval_context'],
                    expected_output=row['expected_output']
                ) for _, row in session_df.iterrows()
            ]
            print(f"Session ID: {session_id}")
            print(f"Test Cases: {llm_test_cases}")
            
            # Create ConversationalTestCase for each session_id
            conv_test_case = ConversationalTestCase(
                chatbot_role=chatbot_role,
                turns=llm_test_cases
            )
            conv_test_case.session_id = session_id
            datasets.append(EvaluationDataset(test_cases=[conv_test_case]))
        return EvaluationDataset()

    async def save_results_deepeval(
        self,
        session_id: List[str],
        metrics_results: List[Tuple[str, float, str, bool]],
        base_dir: str,
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
        filename = f"deepeval_{session_id}_{timestamp}.json"
        json_filepath = os.path.join(base_dir, filename)
        csv_filename = f"deepeval_{session_id}_{timestamp}.csv"
        csv_filepath = os.path.join(base_dir, csv_filename)

        result_data = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
        }
        for metric_name, score, reason, passed in metrics_results:
            result_data["metrics"][metric_name] = {
                "score": score,
                "passed": passed,
                "reason": reason
            }
    
        with open(csv_filepath, 'w', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([
                'Session ID', 'Timestamp', 'Metric', 'Score', 'Passed',
                'Reason',
            ])
        
            # Write rows for each metric
            for metric_name, score, reason, passed in metrics_results:
                csv_writer.writerow([
                    session_id,
                    datetime.now().isoformat(),
                    metric_name,
                    score,
                    'PASSED' if passed else 'FAILED',
                    reason[:500]
                ])
        with open(json_filepath, 'w') as json_file:
            json.dump(result_data, json_file, indent=4)
        
        return {
            "json_path": json_filepath,
            "csv_path": csv_filepath
        }
    

async def load_all_datasets():
    """Load test cases from MongoDB into a dataset."""
    logger.info("Initializing database...")
    mongodb_client = MongoDBClient(SETTINGS.MONGODB_URI)
    await mongodb_client.connect()
    db = mongodb_client.client[cfg.mongodb.db_name]
    chat_history_collection = db[cfg.mongodb.chat_history_collection]
    deepeval = DeepEval(
        chat_history_collection=chat_history_collection
    )
    df = await deepeval.extract_convo_to_df(
        cfg.session_ids, cfg.session_chat_limit
    )
    df = await deepeval.fill_gt_llm(
        df,
        cfg.convo_csv_dir,
        cfg.llm_gt_prompts.system_prompt,
        cfg.llm_gt_prompts.user_prompt
    )
    datasets = await deepeval.load_dataset_from_df(
        df, chatbot_role=cfg.chatbot_role
    )
    return datasets, deepeval


def init_metrics(cfg: DictConfig):
    """Get metrics that are enabled in the config."""
    metrics_list = []
    metrics_config = cfg.metrics
    model = metrics_config.model

    if metrics_config.convo_geval_accuracy.enabled:
        metrics_list.append(ConversationalGEval(
            name="accuracy",
            criteria=metrics_config.convo_geval_accuracy.criteria,
            evaluation_params=[
                LLMTestCaseParams.INPUT,
                LLMTestCaseParams.ACTUAL_OUTPUT,
                LLMTestCaseParams.EXPECTED_OUTPUT
            ],
            threshold=metrics_config.convo_geval_accuracy.threshold,
            model=model,
        ))
    if metrics_config.role_adherence.enabled:
        metrics_list.append(RoleAdherenceMetric(
            threshold=metrics_config.role_adherence.threshold,
            model=model,
        ))
    if metrics_config.knowledge_retention.enabled:
        metrics_list.append(KnowledgeRetentionMetric(
            threshold=metrics_config.knowledge_retention.threshold,
            model=model
        ))
    if metrics_config.conversational_completeness.enabled:
        metrics_list.append(ConversationCompletenessMetric(
            threshold=metrics_config.conversational_completeness.threshold,
            model=model
        ))
    if metrics_config.conversational_relevancy.enabled:
        metrics_list.append(ConversationRelevancyMetric(
            threshold=metrics_config.conversational_relevancy.threshold,
            model=model
        ))
    return metrics_list


datasets, deepeval = asyncio.run(load_all_datasets())
convo_metrics = init_metrics(cfg)


@pytest.mark.parametrize("test_case", datasets)
def test_deepeval(test_case):
    """Evaluate the chatbot on all configured metrics."""
    session_id = getattr(test_case, "session_id", "unknown_session")
    logger.info(f"Evaluating session {session_id}...")

    metrics_results = []
    for metric in convo_metrics:
        metric.measure(test_case)
        metrics_results.append((
            metric.__class__.__name__,
            metric.score,
            metric.reason,
            metric.score >= metric.threshold
        ))
    if cfg.save_results:
        json_filepath, csv_filepath = asyncio.run(
            deepeval.save_results_deepeval(
                session_id,
                metrics_results,
                cfg.deepeval_base_dir
            )
        )
        logger.info(f"Saved evaluation results to {json_filepath}")
        logger.info(f"Saved evaluation results to CSV: {csv_filepath}")