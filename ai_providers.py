from __future__ import annotations

import os
from dataclasses import dataclass
import streamlit as st

class ProviderError(RuntimeError):
    """Visible error when no configured provider can complete a task."""

@dataclass
class ModelReply:
    text: str
    provider: str
    model: str

def get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value:
        return value
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default

class ProviderRouter:
    """OpenAI first; Gemini fallback for quota/rate-limit/transient errors."""
    def __init__(self) -> None:
        self.openai_key = get_setting("OPENAI_API_KEY")
        self.openai_model = get_setting("OPENAI_MODEL", "gpt-4.1-mini")
        self.gemini_key = get_setting("GEMINI_API_KEY")
        self.gemini_model = get_setting("GEMINI_MODEL", "gemini-2.5-flash")

    @staticmethod
    def fallback_worthy(exc: Exception) -> bool:
        message = str(exc).lower()
        phrases = ("rate limit", "rate_limit", "429", "quota", "insufficient_quota", "resource_exhausted", "temporarily unavailable", "service unavailable", "overloaded", "timeout", "timed out", "connection error", "503", "502")
        return any(phrase in message for phrase in phrases)

    def generate(self, system_prompt: str, user_prompt: str) -> ModelReply:
        errors: list[str] = []
        if self.openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_key, timeout=45.0, max_retries=1)
                response = client.responses.create(model=self.openai_model, instructions=system_prompt, input=user_prompt)
                text = getattr(response, "output_text", "") or ""
                if not text.strip():
                    raise RuntimeError("OpenAI returned an empty response.")
                return ModelReply(text, "OpenAI", self.openai_model)
            except Exception as exc:
                errors.append(f"OpenAI {type(exc).__name__}: {exc}")
                if not self.fallback_worthy(exc):
                    raise ProviderError("OpenAI request failed; it did not look like a quota/transient issue. " + errors[-1]) from exc
        else:
            errors.append("OPENAI_API_KEY is not configured.")
        if self.gemini_key:
            try:
                from google import genai
                client = genai.Client(api_key=self.gemini_key)
                response = client.models.generate_content(model=self.gemini_model, contents=f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\nUSER TASK:\n{user_prompt}")
                text = getattr(response, "text", "") or ""
                if not text.strip():
                    raise RuntimeError("Gemini returned an empty response.")
                return ModelReply(text, "Gemini", self.gemini_model)
            except Exception as exc:
                errors.append(f"Gemini {type(exc).__name__}: {exc}")
        else:
            errors.append("GEMINI_API_KEY is not configured.")
        raise ProviderError("No model provider completed the request. " + " | ".join(errors))
