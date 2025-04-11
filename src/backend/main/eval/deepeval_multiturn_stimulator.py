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


async def process_with_tester(input_text):
    tester = CLITester(cfg)
    await tester.initialize()
    await tester.process_query(input_text)
    chat_history = await tester.services.get_chat_history(
        tester.session_id,
        tester.customer_id
    )
    # Get the last assistant message from chat history
    last_turn = chat_history.get_last_turn()
    await tester.services.cleanup()
    return last_turn[1] if last_turn else "No response generated"

tester = None


def model_callback(input_text: str) -> str:
    # Run the async function in a new event loop
    response = asyncio.run(process_with_tester(input_text))
    return response


if __name__ == "__main__":
    logger.info("Running the conversation simulator.")
    convo_simulator.simulate(
        model_callback=model_callback,
        min_turns=2,
        max_turns=5,
        num_conversations=2 
    )
    
    # Optional: Print or save simulated conversations
    for i, convo in enumerate(convo_simulator.simulated_conversations):
        print(f"\n--- Conversation {i+1} ---")
        for turn in convo.turns:
            print(f"User: {turn.input}")
            print(f"Assistant: {turn.output}\n")