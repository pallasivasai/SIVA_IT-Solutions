from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
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
    """Local-first routing when enabled: Ollama, then OpenAI, then Gemini."""
    def __init__(self) -> None:
        self.provider_preference = get_setting("AI_PROVIDER", "auto").strip().lower()
        self.ollama_url = get_setting("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.ollama_model = get_setting("OLLAMA_MODEL", "qwen2.5:7b")
        self.openai_key = get_setting("OPENAI_API_KEY")
        self.openai_model = get_setting("OPENAI_MODEL", "gpt-4.1-mini")
        self.gemini_key = get_setting("GEMINI_API_KEY")
        self.gemini_model = get_setting("GEMINI_MODEL", "gemini-3.5-flash-lite")

    @staticmethod
    def fallback_worthy(exc: Exception) -> bool:
        message = str(exc).lower()
        phrases = ("rate limit", "rate_limit", "429", "quota", "insufficient_quota", "resource_exhausted", "temporarily unavailable", "service unavailable", "overloaded", "timeout", "timed out", "connection error", "503", "502")
        return any(phrase in message for phrase in phrases)

    def _generate_ollama(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> ModelReply:
        payload_data = {
            "model": self.ollama_model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {"temperature": 0.1 if json_mode else 0.2},
        }
        if json_mode:
            payload_data["format"] = "json"
        payload = json.dumps(payload_data).encode("utf-8")
        request = Request(self.ollama_url + "/api/chat", data=payload,
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (URLError, HTTPError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Ollama unavailable at {self.ollama_url} using {self.ollama_model}: {exc}") from exc
        content = result.get("message", {}).get("content", "")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Ollama returned an empty response.")
        return ModelReply(content, "Ollama", self.ollama_model)

    def generate_json(self, system_prompt: str, user_prompt: str) -> ModelReply:
        """Request constrained JSON output where the provider supports it."""
        ollama_first = self.provider_preference == "ollama" or bool(get_setting("OLLAMA_BASE_URL", ""))
        if ollama_first:
            try:
                return self._generate_ollama(system_prompt, user_prompt, json_mode=True)
            except ProviderError:
                if self.provider_preference == "ollama":
                    raise
        if self.openai_key:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_key, timeout=45.0, max_retries=1)
                response = client.responses.create(model=self.openai_model, instructions=system_prompt, input=user_prompt,
                                                   text={"format": {"type": "json_object"}})
                text = getattr(response, "output_text", "") or ""
                if text.strip():
                    return ModelReply(text, "OpenAI", self.openai_model)
            except Exception:
                pass
        if self.gemini_key:
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=self.gemini_key)
                response = client.models.generate_content(model=self.gemini_model,
                    contents=f"SYSTEM INSTRUCTIONS:\\n{system_prompt}\\n\\nUSER TASK:\\n{user_prompt}",
                    config=types.GenerateContentConfig(response_mime_type="application/json"))
                text = getattr(response, "text", "") or ""
                if text.strip():
                    return ModelReply(text, "Gemini", self.gemini_model)
            except Exception:
                pass
        return self.generate(system_prompt, user_prompt)

    def generate(self, system_prompt: str, user_prompt: str) -> ModelReply:
        errors: list[str] = []
        ollama_first = self.provider_preference == "ollama" or bool(os.getenv("OLLAMA_BASE_URL"))
        if ollama_first:
            try:
                return self._generate_ollama(system_prompt, user_prompt)
            except ProviderError as exc:
                errors.append(str(exc))
                if self.provider_preference == "ollama":
                    raise ProviderError("Local Ollama mode failed; cloud providers were not called. " + str(exc)) from exc
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
