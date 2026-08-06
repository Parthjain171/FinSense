"""
LLM provider abstraction.

Uses Groq (Llama 3.3 70B) for the prototype because it is
free, fast, and good enough for financial analysis tasks.

Swap to Claude or GPT-4 for production by changing the
provider in .env. The agent logic and tools are model-agnostic.
Every provider implements the same interface: send a system
prompt and a user message, get a string back.
"""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()  # Load .env into os.environ at import time


class LLMProvider:
    """Base interface. Every provider returns a plain string."""

    def generate(self, system_prompt: str, user_message: str) -> str:
        raise NotImplementedError


class GroqProvider(LLMProvider):
    """
    Groq API running Llama 3.3 70B.
    Free tier. ~500 tokens/sec. Best free option available.
    Sign up at console.groq.com for an API key.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client

    def generate(self, system_prompt: str, user_message: str) -> str:
        if not self.api_key:
            return self._fallback(system_prompt, user_message)

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=1500,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"  Groq API error: {e}. Using template fallback.")
            return self._fallback(system_prompt, user_message)

    def _fallback(self, system_prompt: str, user_message: str) -> str:
        """When no API key is set, return the raw context with a note."""
        return (
            "[LLM not connected. Set GROQ_API_KEY in .env to enable natural language responses.]\n\n"
            "Raw context provided to the agent:\n"
            f"{user_message[:2000]}"
        )


class OpenAIProvider(LLMProvider):
    """
    OpenAI GPT-4 / GPT-4o.
    For production use. Swap by setting LLM_PROVIDER=openai in .env.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model

    def generate(self, system_prompt: str, user_message: str) -> str:
        if not self.api_key:
            return "[OpenAI API key not set]"

        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=1500,
        )
        return response.choices[0].message.content.strip()


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude provider.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model

    def generate(self, system_prompt: str, user_message: str) -> str:
        if not self.api_key:
            return "[Anthropic API key not set]"

        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=1500,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message},
            ],
        )
        return response.content[0].text.strip()


def get_llm_provider() -> LLMProvider:
    """
    Factory function. Picks the right provider based on .env config.
    Defaults to Groq (free tier).
    """
    provider_name = os.getenv("LLM_PROVIDER", "groq").lower()

    if provider_name == "openai":
        return OpenAIProvider()
    elif provider_name == "anthropic":
        return AnthropicProvider()
    else:
        return GroqProvider()
