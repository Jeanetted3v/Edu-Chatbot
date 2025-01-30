"""python -m src.backend.chat_main"""
import logging
import logfire
import sys
import hydra
from omegaconf import DictConfig
import asyncio

from src.backend.utils.logging import setup_logging
from src.backend.chat.intent_classifier import IntentClassifier

logger = logging.getLogger(__name__)
logfire.configure(send_to_logfire='if-token-present')


class CLITester:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.classifier = IntentClassifier()
        self.conversation_history = []

    def print_result(self, query: str, result) -> None:
        """Pretty print the classification result"""
        print("\n" + "="*50)
        print(f"Query: {query}")
        print(f"Intent: {result.intent}")
        print(f"Parameters: {result.parameters}")
        print(f"Is Follow-up: {result.is_followup}")
        print(f"Missing Info: {result.missing_info}")
        print("="*50)

    async def process_query(self, query: str) -> None:
        """Process a single query"""
        # Add to conversation history
        self.conversation_history.append({
            "role": "user",
            "content": query
        })

        # Get classification
        result = await self.classifier.classify(
            query,
            conversation_history=self.conversation_history
        )

        # Print result
        self.print_result(query, result)

        # Add simulated response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": f"Processed query with intent: {result.intent}"
        })

    def run(self) -> None:
        """Run the CLI tester"""
        print("\nWelcome to the Intent Classifier Tester!")
        print("Type 'quit' or 'exit' to end the session")
        print("Type 'clear' to clear conversation history")
        print("Type 'history' to see conversation history\n")

        while True:
            try:
                query = input("\nEnter your query: ").strip()

                if query.lower() in ['quit', 'exit']:
                    print("Goodbye!")
                    break
                
                elif query.lower() == 'clear':
                    self.conversation_history = []
                    print("Conversation history cleared!")
                    continue
                
                elif query.lower() == 'history':
                    print("\nConversation History:")
                    for msg in self.conversation_history:
                        print(f"{msg['role']}: {msg['content']}")
                    continue

                elif not query:
                    continue

                # Process the query
                asyncio.run(self.process_query(query))

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                logging.error(f"Error processing query: {e}")
                print(f"Error: {e}")


@hydra.main(
    version_base=None,
    config_path="../../config",
    config_name="chat")
def main(cfg) -> None:
    logger = logging.getLogger(__name__)
    logger.info("Setting up logging configuration.")
    setup_logging()

    try:
        tester = CLITester(cfg)
        tester.run()
    except Exception as e:
        logger.error(f"Error running CLI tester: {e}")
        print(f"Error running CLI tester: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()