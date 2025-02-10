import logging
from datetime import datetime
from typing import List, Dict


logger = logging.getLogger(__name__)


class ChatHistory:
    def __init__(self, max_turns_for_prompt: int = 30):
        self.conversation_turns = []
        self.max_turns_for_prompt = max_turns_for_prompt
        self._last_processed_timestamp = None  # Track last processed message

    def add_turn(self, role: str, content: str) -> None:
        """Add a turn to conversation history with full metadata for MongoDB"""
        self.conversation_turns.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })

    def format_history_for_prompt(self) -> str:
        """Format last N turns in simple format for prompt to save tokens"""
        recent_turns = self.conversation_turns[-self.max_turns_for_prompt:]
        return "\n".join(
            f"{turn['role'].capitalize()}: {turn['content']}"
            for turn in recent_turns
        )

    def get_full_history(self) -> List[Dict]:
        """Get full conversation history for MongoDB storage"""
        return self.conversation_turns
    
    def _has_similar_message(self, role: str, content: str, similarity_threshold: float = 0.9) -> bool:
            """Check if a similar message already exists using fuzzy matching"""
            from difflib import SequenceMatcher
            
            content = content.strip()
            for turn in self.conversation_turns:
                if turn['role'] == role:
                    similarity = SequenceMatcher(None, turn['content'].strip(), content).ratio()
                    if similarity >= similarity_threshold:
                        return True
            return False

    def process_msg_history(self, message_history: List[Dict]) -> None:
        """Process and add message history to conversation turns"""
        if not message_history:
            return
            
        for msg in message_history:
            timestamp = getattr(msg, 'timestamp', datetime.now().isoformat())
            # Skip if we've already processed this message
            if self._last_processed_timestamp and timestamp <= self._last_processed_timestamp:
                continue
            if hasattr(msg, 'role') and msg.role == 'user':
                content = msg.content
                if "Current query: " in content:
                    content = content.split("Current query: ")[-1].split("\n")[0]
                # Use fuzzy matching to avoid duplicates
                if not self._has_similar_message('user', content):
                    self.add_turn('user', content.strip())
            elif hasattr(msg, 'parts'):
                # Handle response messages
                response_content = next(
                    (part.content for part in msg.parts 
                     if part.part_kind == 'text'),
                    None
                )
                if response_content and not self._has_similar_message('assistant', response_content):
                    self.add_turn('assistant', response_content.strip())
                
                self._last_processed_timestamp = timestamp
        
        