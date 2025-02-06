from src.backend.utils.settings import SETTINGS
from openai import OpenAI


class LLM():
    def __init__(self):
        self.openai_api_key = SETTINGS.OPENAI_API_KEY
        self.client = OpenAI(api_key=self.openai_api_key)

    def llm(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = 'gpt-4o-mini',
        temperature: float = 0.2
    ) -> str:
        response = self.client.chat.completions.create(
           messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
           model=model,
           temperature=temperature,
        #    stream=True
        )
        content = response.choices[0].message.content
        return content
