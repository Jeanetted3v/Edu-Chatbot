import yaml
import os
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class PromptLoader:
    _prompts: Dict[str, Dict[str, str]] = {}
    
    @classmethod
    def load_prompts(
        cls,
        prompt_name: str
    ) -> Dict[str, str]:
        """
        Load prompts from YAML file
        
        Args:
            prompt_name: Name of the prompt file (without .yaml extension)
            
        Returns:
            Dictionary containing the loaded prompts
            
        Raises:
            FileNotFoundError: If check_exists is True and & file doesn't exist
        """
        if prompt_name not in cls._prompts:
            prompt_path = (
                Path(__file__).parent.parent
                / "prompts"
                / f"{prompt_name}.yaml"
            )
            if not prompt_path.exists():
                raise FileNotFoundError(f"Prompt file {prompt_name}.yaml"
                                        f"not found")
                
            with open(prompt_path, 'r') as f:
                cls._prompts[prompt_name] = yaml.safe_load(f)
                
        return cls._prompts[prompt_name]