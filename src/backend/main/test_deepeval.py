"""To run:
deepeval test run src/backend/main/test_deepeval.py
Parallelization (e.g. n=4): -n 4
Use Cache with: -c
Verbose mode: -v
"""
import logging
from omegaconf import DictConfig
from hydra import initialize, compose
import asyncio
import pytest

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

from src.backend.utils.settings import SETTINGS
from src.backend.utils.logging import setup_logging
from src.backend.database.mongodb_client import MongoDBClient
from src.backend.evaluation.eval_utils import EvalUtils


logger = logging.getLogger(__name__)
logger.info("Setting up logging configuration.")
setup_logging()
initialize(version_base=None, config_path="../../../config")
cfg = compose(config_name="eval")


async def load_dataset():
    """Load test cases from MongoDB into a dataset."""
    logger.info("Initializing database...")
    mongodb_client = MongoDBClient(SETTINGS.MONGODB_URI)
    await mongodb_client.connect()
    db = mongodb_client.client[cfg.mongodb.db_name]
    chat_history_collection = db[cfg.mongodb.chat_history_collection]
    utils = EvalUtils(
        chat_history_collection=chat_history_collection
    )
    dataset = await utils.create_dataset_deepeval(
        session_ids=cfg.session_ids,
        chatbot_role=cfg.chatbot_role,
        session_chat_limit=cfg.session_chat_limit
    )
    return dataset


def init_metrics(cfg: DictConfig):
    """Get metrics that are enabled in the config."""
    metrics_list = []
    metrics_config = cfg.metrics
    model = metrics_config.model

    if metrics_config.convo_geval_accuracy.enabled:
        metrics_list.append(ConversationalGEval(
            threshold=metrics_config.convo_geval_accuracy.threshold,
            model=model,
            expected_output=metrics_config.convo_geval_accuracy.expected_output,
            context=metrics_config.convo_geval_accuracy.context,
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


dataset = asyncio.run(load_dataset())
convo_metrics = init_metrics(cfg)


@pytest.mark.parametrize("test_case", dataset)
def test_deepeval(test_case):
    """Evaluate the chatbot on all configured metrics."""
    session_id = getattr(test_case, "id", "unknown_session")
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
            EvalUtils.save_results_deepeval(
                metrics_results, cfg.deepeval_base_dir, test_case
                )
        )
        logger.info(f"Saved evaluation results to {json_filepath}")
        logger.info(f"Saved evaluation results to CSV: {csv_filepath}")
