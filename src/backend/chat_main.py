"""python -m src.backend.chat_main"""
import logging
import logfire
import hydra
import asyncio
from omegaconf import DictConfig
import asyncio

from src.backend.utils.logging import setup_logging
from src.backend.chat.intent_classifier import IntentClassifier
from src.backend.models.intent import IntentResult

logger = logging.getLogger(__name__)
logfire.configure(send_to_logfire='if-token-present')


class CLITester:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.classifier = IntentClassifier()
        self.message_history = []

    def print_result(self, result: IntentResult) -> None:
        """Pretty print the classification result"""
        print("\n" + "="*50)
        if result.missing_info:
            print(f"Question: {result.response}")
        else:
            print(f"Intent: {result.intent}")
            print(f"Parameters: {result.parameters}")
            print(f"Response: {result.response}")
        print("="*50)

    async def process_query(self, query: str) -> None:
        """Process a single query"""
        # Add user query to history
        self.message_history.append({
            "role": "user",
            "content": query
        })
        
        # Get classification that handles the entire conversation flow
        result = await self.classifier.get_intent(query)
        self.print_result(result)
        
        # Add assistant response to history
        if result.missing_info:
            response_content = result.response  # The question asking for missing info
        else:
            response_content = f"Intent: {result.intent}, Response: {result.response}"
            
        self.message_history.append({
            "role": "assistant",
            "content": response_content
        })

    async def run(self) -> None:
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
                await self.process_query(query)

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

    async def async_main():
        tester = CLITester(cfg)
        await tester.run()
    
    asyncio.run(async_main())


if __name__ == "__main__":
    main()