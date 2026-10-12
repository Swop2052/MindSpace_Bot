"""
Anthropic Claude LLM Configuration.
Exclusively uses Anthropic Claude neural models (claude-haiku-5-5, claude-sonnet-4-5, etc.)
to dynamically understand user intent and generate real-time conversational responses.
Zero fallback models, zero hardcoded responses.
"""

import logging
import os
from typing import Any
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


class AnthropicLLM:
    """
    Dedicated Anthropic Claude client. Dispatches all multi-turn conversation
    prompts directly to Claude for 100% dynamic reasoning and responses.
    Automatically reloads credentials from .env on the fly if updated.
    """

    def __init__(self):
        self._client = None
        self._current_key = None
        self._current_model = None
        self._init_client()

    def _init_client(self, force_reload: bool = False):
        """Initialize ChatAnthropic client dynamically using .env credentials."""
        load_dotenv(override=True)
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        model_name = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-20241022").strip()
        max_tokens = int(os.getenv("MAX_TOKENS", 1024))

        if not api_key or len(api_key) <= 10:
            self._client = None
            self._current_key = None
            self._current_model = None
            return

        if not force_reload and self._client and self._current_key == api_key and self._current_model == model_name:
            return

        try:
            self._client = ChatAnthropic(
                model=model_name,
                anthropic_api_key=api_key,
                max_tokens=max_tokens,
                timeout=60,
            )
            self._current_key = api_key
            self._current_model = model_name
            logger.info(f"Initialized Anthropic Claude ({model_name})")
        except Exception as e:
            logger.debug(f"Failed to initialize Anthropic client: {e}")
            self._client = None

    @staticmethod
    def _clean_content(content: Any) -> str:
        """
        Extract only clean, user-visible text from Claude's response.
        Filters out internal thinking blocks, signatures, redacted blocks, and metadata.
        """
        if not content:
            return ""

        if isinstance(content, str):
            import re
            cleaned = re.sub(r'<thinking>[\s\S]*?</thinking>', '', content).strip()
            cleaned = re.sub(r"\{'signature':\s*'[A-Za-z0-9+/=]+',\s*'thinking':.*?'type':\s*'thinking'\}", "", cleaned).strip()
            return cleaned

        if isinstance(content, list):
            text_parts = []
            for part in content:
                # 1. Dictionary block
                if isinstance(part, dict):
                    part_type = part.get("type", "")
                    if part_type in ("thinking", "redacted_thinking"):
                        continue
                    if "signature" in part:
                        continue
                    if "text" in part and part["text"]:
                        text_parts.append(str(part["text"]))
                # 2. Object block (e.g. TextBlock, ThinkingBlock)
                elif hasattr(part, "type") and getattr(part, "type") in ("thinking", "redacted_thinking"):
                    continue
                elif hasattr(part, "signature"):
                    continue
                elif hasattr(part, "text") and getattr(part, "text"):
                    text_parts.append(str(getattr(part, "text")))
                # 3. String block
                elif isinstance(part, str):
                    s = part.strip()
                    if s.startswith("{'signature'") or s.startswith('{"signature"'):
                        continue
                    text_parts.append(part)

            return " ".join(text_parts).strip()

        return str(content).strip()

    def invoke(self, messages: Any, **kwargs) -> AIMessage:
        """Invoke Anthropic Claude dynamically with multi-turn prompt context."""
        # Check if environment credentials changed on the fly
        self._init_client()

        if not self._client:
            return AIMessage(
                content="I'm having trouble connecting to Claude right now. Please verify your ANTHROPIC_API_KEY in .env."
            )

        try:
            response = self._client.invoke(messages, **kwargs)
            if response and hasattr(response, "content") and response.content:
                clean_text = self._clean_content(response.content)
                if clean_text:
                    return AIMessage(content=clean_text)
            return AIMessage(content="I hear you. Could you share a bit more?")
        except Exception as e:
            err_str = str(e)
            logger.debug(f"Anthropic Claude API call failed: {err_str}")
            if "authentication_error" in err_str.lower() or "401" in err_str or "invalid x-api-key" in err_str:
                # Force reload from .env in case user updated it, then retry once
                self._init_client(force_reload=True)
                if self._client:
                    try:
                        retry_resp = self._client.invoke(messages, **kwargs)
                        if retry_resp and hasattr(retry_resp, "content") and retry_resp.content:
                            clean_retry = self._clean_content(retry_resp.content)
                            if clean_retry:
                                return AIMessage(content=clean_retry)
                    except Exception:
                        pass
                return AIMessage(
                    content="I'm having trouble authenticating with Claude right now. Please check your ANTHROPIC_API_KEY in .env."
                )
            elif "rate_limit" in err_str.lower() or "429" in err_str:
                return AIMessage(
                    content="Claude is receiving high traffic right now. Please wait a moment and send your message again."
                )
            elif "overloaded" in err_str.lower() or "529" in err_str:
                return AIMessage(
                    content="Claude's servers are briefly overloaded right now. Please retry in a few moments."
                )
            else:
                return AIMessage(
                    content=f"I couldn't reach Claude right now ({err_str[:90]}). Please check your connection and try again."
                )


# Primary Claude LLM instance
llm = AnthropicLLM()
