import logging
import hydra
import asyncio
from typing import List, Dict, Optional
from omegaconf import DictConfig
from src.backend.utils.logging import setup_logging
from src.backend.chat.service_container import ServiceContainer
from src.backend.evaluation.ragas import RagasEvaluator


logger = logging.getLogger(__name__)
logger.info("Setting up logging configuration.")
setup_logging()


async def evaluate_session(
    session_chat_limit: int,
    services: ServiceContainer,
    ragas_base_dir: str,
    session_id: str
):
    
    evaluator = RagasEvaluator(services)
    logger.info(f"Evaluating session {session_id}...")
    try:
        results = await evaluator.single_session_eval(
            session_id, session_chat_limit
        )
        eval_folder = await evaluator.save_evaluation_results(
            results, base_dir=ragas_base_dir
        )
        
        logger.info("\n===== RAGAS Evaluation Results =====")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Message count: {results.get('message_count', 0)}")
        logger.info(f"Conversation pairs: {results.get('conversation_pairs', 0)}")
        
        if 'metrics' in results and results['metrics']:
            logger.info("\nMetrics:")
            for metric, score in results['metrics'].items():
                logger.info(f"  {metric}: {score:.4f}")
        
        logger.info(f"Evaluation results saved to: {eval_folder}")
        return {"status": "success", "result": results}
    
    except Exception as e:
        logger.error(f"Error evaluating session {session_id}: {e}")
        return {"status": "error", "error": str(e)}
    
@hydra.main(
    version_base=None,
    config_path="../../../config",
    config_name="eval")
def main(cfg: DictConfig) -> None:
    async def run_evaluation():
        logger.info("Initializing services...")
        services = ServiceContainer(cfg)
        await services.initialize()

        for session_id in cfg.session_ids:
            await evaluate_session(
                session_chat_limit=cfg.session_chat_limit,
                services=services,
                ragas_base_dir=cfg.ragas_base_dir,
                session_id=session_id
            )

    asyncio.run(run_evaluation())


if __name__ == "__main__":
    main()