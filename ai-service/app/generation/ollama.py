"""
Ollama LLM Provider — local inference on Apple Silicon.

Free, local, no API key required.
Model is configurable via LLM_MODEL env var.
Recommended for M2 MacBook Air: mistral (7B) or llama3.2:3b (smaller/faster)
"""

import json
import logging
from dataclasses import dataclass
from typing import Optional
import ollama
from .prompts.legal_research_prompt import SYSTEM_PROMPT
from ..core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class LLMResponse:
    raw_text: str
    answer: str
    citations: list[dict]
    confidence: str = "MEDIUM"
    disclaimer: str = ""
    parse_error: Optional[str] = None


class OllamaProvider:
    """
    Wraps Ollama for structured JSON output.

    The LLM is instructed to return JSON only.
    We parse and validate the output before returning it.
    """

    def __init__(self):
        self.model = settings.llm_model
        self.base_url = settings.ollama_base_url
        self._client = ollama.Client(host=self.base_url)
        logger.info("OllamaProvider initialised — model: %s, url: %s", self.model, self.base_url)

    def generate(self, user_prompt: str) -> LLMResponse:
        """
        Generate a response. Enforces JSON output via system prompt.
        Falls back gracefully if JSON parsing fails.
        """
        try:
            response = self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                options={
                    "temperature": 0.1,   # Low temperature for factual legal research
                    "top_p": 0.9,
                    "num_ctx": 4096,
                },
            )
            # ollama >= 0.2 returns ChatResponse objects (not dicts)
            try:
                raw_text = response.message.content
            except AttributeError:
                # Fallback for older SDK versions or dict-like responses
                raw_text = response["message"]["content"]
            return self._parse_response(raw_text)

        except Exception as exc:
            logger.error("Ollama generation failed: %s", exc)
            return LLMResponse(
                raw_text="",
                answer="GENERATION_ERROR",
                citations=[],
                parse_error=str(exc),
            )

    def generate_with_system(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """
        Generate a response using a custom system prompt.
        Used by Phase 3 endpoints (comparison, precedents, provision, brief)
        that each have their own task-specific system prompt.
        """
        try:
            response = self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                options={
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_ctx": 4096,
                },
            )
            try:
                raw_text = response.message.content
            except AttributeError:
                raw_text = response["message"]["content"]
            return self._parse_response(raw_text)

        except Exception as exc:
            logger.error("Ollama generation (with custom system) failed: %s", exc)
            return LLMResponse(
                raw_text="",
                answer="GENERATION_ERROR",
                citations=[],
                parse_error=str(exc),
            )

    def _parse_response(self, raw_text: str) -> LLMResponse:
        """Parse the LLM's JSON output, with fallback for malformed responses."""
        cleaned = raw_text.strip()
        # Strip markdown code fences if present (defensive)
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned

        try:
            data = json.loads(cleaned)
            return LLMResponse(
                raw_text=raw_text,
                answer=data.get("answer", ""),
                citations=data.get("citations", []),
                confidence=data.get("confidence", "MEDIUM"),
                disclaimer=data.get("disclaimer", ""),
            )
        except json.JSONDecodeError as exc:
            logger.warning("LLM response was not valid JSON: %s", exc)
            return LLMResponse(
                raw_text=raw_text,
                answer=raw_text,
                citations=[],
                parse_error=f"JSON parse error: {exc}",
            )

    def check_availability(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            list_response = self._client.list()
            # ollama >= 0.2 returns ListResponse object; each entry has .model attr
            try:
                available = [m.model for m in list_response.models]
            except AttributeError:
                # Fallback for dict-style response (older SDK)
                available = [m["name"] for m in list_response.get("models", [])]
            if self.model not in available and not any(
                m.startswith(self.model.split(":")[0]) for m in available
            ):
                logger.warning(
                    "Model '%s' not found in Ollama. Available: %s. "
                    "Run: docker exec lexrag-ollama ollama pull %s",
                    self.model, available, self.model,
                )
                return False
            return True
        except Exception as exc:
            logger.error("Cannot reach Ollama at %s: %s", self.base_url, exc)
            return False
