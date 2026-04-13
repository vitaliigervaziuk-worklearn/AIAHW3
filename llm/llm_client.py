from google import genai
from typing import Optional
from dotenv import load_dotenv



class LLMClient:
    """
    Central wrapper for all LLM calls.
    Uses the supported google-genai SDK.
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash-lite",
        temperature: float = 0.0,
    ):
        load_dotenv()
        self.model = model
        self.temperature = temperature
        self.client = genai.Client()  # reads GOOGLE_API_KEY automatically

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:

        if system_prompt:
            prompt = f"{system_prompt}\n\n{prompt}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config={
                "temperature": self.temperature,
            },
        )

        return response.text.strip()