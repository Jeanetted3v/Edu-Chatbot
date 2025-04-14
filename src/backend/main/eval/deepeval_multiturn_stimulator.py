"""To run:
python -m src.backend.main.eval.deepeval_multiturn_stimulator
"""
import logging
import asyncio
from hydra import initialize, compose
from deepeval.conversation_simulator import ConversationSimulator
from src.backend.main.chat_main import CLITester
from src.backend.utils.logging import setup_logging

user_profile_items = ["parent", "age of kid", "course interested in"]
user_intentions = [
    "find out about relevant course",
    "find out about course details",
    "find out which teacher is teaching my kid",
    "find out the price of course interested in",
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

print("Initializing tester...")
tester = CLITester(cfg)
loop = asyncio.new_event_loop()
loop.run_until_complete(tester.initialize())


async def model_callback(input_text: str) -> str:
    try:
        tester = CLITester(cfg)
        await tester.services.initialize()
        query = input_text
        await tester.process_query(query)
    except Exception as e:
        logger.error(f"Error in model callback: {e}")
        return "An error occurred while processing your request."
    finally:
        await tester.services.cleanup()


async def main():
    try:
        logger.info("Running the conversation simulator.")
        await convo_simulator.simulate(
            model_callback=model_callback,
            min_turns=2,
            max_turns=5,
            num_conversations=1
        )
        
        # Optional: Print or save simulated conversations
        for i, convo in enumerate(convo_simulator.simulated_conversations):
            print(f"\n--- Conversation {i+1} ---")
            for turn in convo.turns:
                print(f"User: {turn.input}")
                print(f"Assistant: {turn.output}\n")
    except Exception as e:
        logger.error(f"Error during conversation simulation: {e}")
        await tester.services.cleanup()
    finally:
        await tester.services.cleanup()
        loop.close()


if __name__ == "__main__":
    asyncio.run(main())