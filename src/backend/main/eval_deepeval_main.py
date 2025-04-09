"""To run:
python -m src.backend.main.eval_deepeval_main
"""
import logging
import os
from datetime import datetime
import hydra
import asyncio
from omegaconf import DictConfig
from src.backend.utils.logging import setup_logging
from src.backend.utils.settings import SETTINGS
from src.backend.database.mongodb_client import MongoDBClient
from src.backend.evaluation.deepeval_utils import EvalUtils


logger = logging.getLogger(__name__)
logger.info("Setting up logging configuration.")
setup_logging()


async def convert_msg_to_csv(cfg: DictConfig) -> None:
    """Convert customer and bot messages, retrieved context to CSV format.
    After this, need to manually fill in expected_output, before evaluating
    using DeepEval.
    """
    logger.info("Initializing database...")
    mongodb_client = MongoDBClient(SETTINGS.MONGODB_URI)
    await mongodb_client.connect()
    db = mongodb_client.client[cfg.mongodb.db_name]
    chat_history_collection = db[cfg.mongodb.chat_history_collection]
    utils = EvalUtils(
        chat_history_collection=chat_history_collection
    )
    convo_csv_file_name = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.csv"
    convo_csv_file_path = os.path.join(
        cfg.convo_csv_dir,
        convo_csv_file_name
    )
    os.makedirs(cfg.convo_csv_dir, exist_ok=True)
    await utils.export_convo_to_csv(
        session_ids=cfg.session_ids,
        output_file=convo_csv_file_path,
        session_chat_limit=cfg.session_chat_limit
    )
    return None


@hydra.main(
    version_base=None,
    config_path="../../../config",
    config_name="eval")
def main(cfg: DictConfig) -> None:
    asyncio.run(convert_msg_to_csv(cfg))
    logger.info("Conversion complete.")


if __name__ == "__main__":
    main()