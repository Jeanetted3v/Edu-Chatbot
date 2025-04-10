

import logging
import logfire
import hydra
import asyncio
from hydra import initialize, compose
from deepeval.conversation_simulator import ConversationSimulator
from src.backend.main.chat_main import CLITester
from src.backend.utils.logging import setup_logging

user_profile_items = ["parent", "age of kid", "course interested in"]
user_intentions = [
    "check relevant course",
    "check course details",
    "check which teacher is teaching my kid",
    "check course price",
    "check course format",
    "check course schedule"
]

convo_simulator = ConversationSimulator(
    user_profile_items=user_profile_items,
    user_intentions=user_intentions,
    simulator_model="gpt-4o-mini",
)

logger = logging.getLogger(__name__)
logger.info("Setting up logging configuration.")
setup_logging()
initialize(version_base=None, config_path="../../../../config")
cfg = compose(config_name="config")


def model_callback(cfg, input: str) -> str:
    async def async_main():
        tester = CLITester(cfg)
        await tester.run()
    asyncio.run(async_main())
    return f"I don't know how to answer this: {input}"


convo_simulator.simulate(model_callback=model_callback)