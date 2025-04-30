"""To run:
python -m src.creator.main_chatbot_creator
"""

import hydra
import logging
from omegaconf import DictConfig
import asyncio
from src.backend.utils.logging import setup_logging
from src.creator.chatbot_creator import ChatbotCreator

logger = logging.getLogger(__name__)
setup_logging()


async def main_async(cfg: DictConfig) -> None:
    mode = cfg.get("mode", "optimizer")  # default to optimize if not specified
    chatbot_creator = ChatbotCreator(cfg)

    if mode == "optimize":
        await chatbot_creator.optimize_prompt(cfg)
    elif mode == "create":
        await chatbot_creator.chatbot_creation()


@hydra.main(
    version_base=None,
    config_path="../../../config",
    config_name="creator")
def main(cfg) -> None:
    asyncio.run(main_async(cfg))


if __name__ == "__main__":
    main()


