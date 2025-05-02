"""
Shared application state for the chatbot creator.
"""
from pathlib import Path
from hydra import compose, initialize_config_dir


def load_config():
    current_file_path = Path(__file__).resolve()
    project_root = current_file_path.parent.parent.parent
    config_dir = project_root / "config"

    with initialize_config_dir(
        config_dir=str(config_dir),
        job_name="Create Chatbot"
    ):
        cfg = compose(config_name="config")
    return cfg


state = {
    "summary": "",
    "sim_prompt": "",
    "chat_prompt": "",
    "conversations": [],
    "current_conv_index": 0,
    "feedback_history": [],
    "model_name": "gpt-4o-mini",  # Default model name
    "regeneration_count": 0
}


def get(key, default=None):
    """Get a value from the application state."""
    return state.get(key, default)


def set(key, value):
    """Set a value in the application state."""
    state[key] = value
    return value


def update(data):
    """Update multiple values in the application state."""
    state.update(data)
    return state