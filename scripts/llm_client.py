"""
llm_client.py — LLM abstraction layer over Ollama / Claude / Gemini / OpenRouter.

The four AI pipeline stages (topic_selection, article_synthesis, translation,
quiz_generation) read their provider/model from scripts/ai_config.yaml and
get a client via get_client_for_stage(). Each stage may also have a fallback
client.

A failed JSON parse is the most common failure mode — clean_json_response()
strips markdown fences and preambles before json.loads() is attempted.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AI_CONFIG_FILE = PROJECT_ROOT / "scripts" / "ai_config.yaml"
# UI-managed override; if this file exists, it takes precedence over ai_config.yaml.
# Written by the admin settings page (src/pages/admin/settings.astro).
AI_SETTINGS_OVERRIDE = PROJECT_ROOT / "data" / "config" / "ai_settings.json"
ENV_FILE = PROJECT_ROOT / ".env"

# Load .env once at module import. Missing file is fine (only Ollama needed
# for the default config and Ollama doesn't read from .env aside from host).
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


# =============================================================================
# Data models
# =============================================================================


@dataclass
class LLMResponse:
    content: str
    tokens_used: int
    duration_sec: float
    provider: str
    model: str


@dataclass
class StageConfig:
    """Resolved configuration for one pipeline stage."""

    provider: str
    model: str
    temperature: float
    max_tokens: int
    fallback: "StageConfig | None" = None


# =============================================================================
# Provider clients
# =============================================================================


class BaseLLMClient(ABC):
    """Common interface every provider implements."""

    name: str = "base"
    model: str = ""

    @abstractmethod
    def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.5,
        max_tokens: int = 2000,
        response_format: str = "json",
    ) -> LLMResponse:
        """Send a prompt and return one parsed response.

        response_format: "json" hints the provider to enforce JSON output where
        supported. Even with this hint, callers should still defensively run
        clean_json_response() / parse_json_response() on the content.
        """
        ...

    def __repr__(self) -> str:  # nicer logging
        return f"{self.name}({self.model})"


class OllamaClient(BaseLLMClient):
    name = "ollama"

    def __init__(self, model: str):
        import ollama

        self.model = model
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self._client = ollama.Client(host=self.host)

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.5,
        max_tokens: int = 2000,
        response_format: str = "json",
    ) -> LLMResponse:
        started = time.monotonic()
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            # Qwen3 defaults to "thinking" mode (outputs <think>...</think>
            # before the answer). For our pipeline this just wastes tokens and
            # makes timing 2-5x slower; we disable it here. If a future stage
            # benefits from reasoning, override per-call.
            "think": False,
        }
        if response_format == "json":
            kwargs["format"] = "json"

        resp = self._client.chat(**kwargs)
        duration = time.monotonic() - started

        content = resp["message"]["content"]
        tokens = int(resp.get("eval_count", 0) or 0) + int(
            resp.get("prompt_eval_count", 0) or 0
        )

        return LLMResponse(
            content=content,
            tokens_used=tokens,
            duration_sec=duration,
            provider=self.name,
            model=self.model,
        )


class ClaudeClient(BaseLLMClient):
    name = "claude"

    def __init__(self, model: str):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "未設定 ANTHROPIC_API_KEY 環境變數。\n"
                "如要使用 Claude，請去 console.anthropic.com 申請 API key，"
                "然後在 .env 加上：\n"
                "    ANTHROPIC_API_KEY=sk-ant-..."
            )
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self.model = model

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.5,
        max_tokens: int = 2000,
        response_format: str = "json",
    ) -> LLMResponse:
        started = time.monotonic()

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        resp = self._client.messages.create(**kwargs)
        duration = time.monotonic() - started

        content = resp.content[0].text  # type: ignore[union-attr]
        tokens = int(resp.usage.input_tokens) + int(resp.usage.output_tokens)

        return LLMResponse(
            content=content,
            tokens_used=tokens,
            duration_sec=duration,
            provider=self.name,
            model=self.model,
        )


class GeminiClient(BaseLLMClient):
    name = "gemini"

    def __init__(self, model: str):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "未設定 GEMINI_API_KEY 環境變數。\n"
                "請去 aistudio.google.com 申請免費 API key（不需綁信用卡），"
                "然後在 .env 加上：\n"
                "    GEMINI_API_KEY=AIzaSy..."
            )
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self.model = model

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.5,
        max_tokens: int = 2000,
        response_format: str = "json",
    ) -> LLMResponse:
        from google.genai import types

        started = time.monotonic()

        # Default Gemini safety filters block normal news coverage of war,
        # crime, conflict, etc. Since our source material is mainstream news
        # (BBC, Reuters, AP, …) we relax to BLOCK_ONLY_HIGH so news of
        # military events / political conflict can be summarised.
        safety_settings = [
            types.SafetySetting(
                category=t, threshold="BLOCK_ONLY_HIGH"
            )
            for t in (
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            )
        ]

        # Gemini 2.5 series has internal "thinking" tokens enabled by default.
        # On gemini-2.5-flash, ~3800 thinking tokens chew through max_output_tokens
        # before the model emits any visible JSON, so output gets truncated mid-
        # string. Disable thinking for our pipeline (deterministic news work).
        thinking_config = types.ThinkingConfig(thinking_budget=0)

        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "safety_settings": safety_settings,
            "thinking_config": thinking_config,
        }
        if system:
            config_kwargs["system_instruction"] = system
        if response_format == "json":
            config_kwargs["response_mime_type"] = "application/json"

        # Gemini's free tier sporadically returns 503 (capacity) or 429
        # (per-minute rate limit). Retry up to 2 times with short backoff
        # before bubbling up to the pipeline-level fallback.
        last_err: Exception | None = None
        resp = None
        for retry_idx in range(3):
            if retry_idx > 0:
                time.sleep(2 ** retry_idx)  # 2s, then 4s
            try:
                resp = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                break
            except Exception as e:
                msg = str(e)
                # Only retry on transient server-side issues
                if any(s in msg for s in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED")):
                    last_err = e
                    continue
                raise
        if resp is None:
            raise last_err if last_err else RuntimeError("Gemini call failed silently")
        duration = time.monotonic() - started

        content = resp.text or ""
        usage = getattr(resp, "usage_metadata", None)
        tokens = int(getattr(usage, "total_token_count", 0) or 0) if usage else 0

        return LLMResponse(
            content=content,
            tokens_used=tokens,
            duration_sec=duration,
            provider=self.name,
            model=self.model,
        )


class OpenRouterClient(BaseLLMClient):
    name = "openrouter"

    def __init__(self, model: str):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "未設定 OPENROUTER_API_KEY 環境變數。\n"
                "請去 openrouter.ai 申請 API key，然後在 .env 加上：\n"
                "    OPENROUTER_API_KEY=sk-or-..."
            )
        self.api_key = api_key
        self.model = model

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.5,
        max_tokens: int = 2000,
        response_format: str = "json",
    ) -> LLMResponse:
        import httpx

        started = time.monotonic()

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format == "json":
            body["response_format"] = {"type": "json_object"}

        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/personal/english-news-reader",
                "X-Title": "English News Reader",
            },
            json=body,
            timeout=120.0,
        )
        resp.raise_for_status()
        data = resp.json()
        duration = time.monotonic() - started

        content = data["choices"][0]["message"]["content"]
        tokens = int(data.get("usage", {}).get("total_tokens", 0) or 0)

        return LLMResponse(
            content=content,
            tokens_used=tokens,
            duration_sec=duration,
            provider=self.name,
            model=self.model,
        )


# =============================================================================
# Factories — read ai_config.yaml, construct clients on demand
# =============================================================================


_PROVIDERS: dict[str, type[BaseLLMClient]] = {
    "ollama": OllamaClient,
    "claude": ClaudeClient,
    "gemini": GeminiClient,
    "openrouter": OpenRouterClient,
}

_CLIENT_CACHE: dict[tuple[str, str], BaseLLMClient] = {}
_CONFIG_CACHE: dict[str, Any] | None = None


def load_config() -> dict[str, Any]:
    """Read AI config: prefer the UI-managed JSON override, fall back to YAML defaults.

    Resolution order:
      1. data/config/ai_settings.json   (written by /admin/settings page)
      2. scripts/ai_config.yaml         (canonical defaults with comments)
    """
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    if AI_SETTINGS_OVERRIDE.exists():
        try:
            _CONFIG_CACHE = json.loads(
                AI_SETTINGS_OVERRIDE.read_text(encoding="utf-8")
            )
            print(f"📋 使用 UI 自訂設定：{AI_SETTINGS_OVERRIDE.relative_to(PROJECT_ROOT)}")
            return _CONFIG_CACHE
        except Exception as e:
            print(
                f"⚠️ 讀取 {AI_SETTINGS_OVERRIDE.relative_to(PROJECT_ROOT)} 失敗（{e}），"
                f"改用 {AI_CONFIG_FILE.relative_to(PROJECT_ROOT)} 預設值",
                file=sys.stderr,
            )

    if not AI_CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"找不到 AI 設定檔：{AI_CONFIG_FILE}\n"
            "這個檔案應該由 Phase 3 setup 建立。"
        )
    _CONFIG_CACHE = yaml.safe_load(AI_CONFIG_FILE.read_text(encoding="utf-8"))
    return _CONFIG_CACHE


def make_client(provider: str, model: str) -> BaseLLMClient:
    """Build (or reuse) a client for a (provider, model) pair."""
    key = (provider, model)
    if key in _CLIENT_CACHE:
        return _CLIENT_CACHE[key]
    cls = _PROVIDERS.get(provider)
    if cls is None:
        raise ValueError(
            f"未知 provider: {provider!r}（可選：{', '.join(_PROVIDERS.keys())}）"
        )
    client = cls(model=model)
    _CLIENT_CACHE[key] = client
    return client


def stage_config(stage_name: str) -> StageConfig:
    """Resolve provider + fallback config for one pipeline stage."""
    cfg = load_config()
    pipeline = cfg.get("ai_pipeline") or {}
    if stage_name not in pipeline:
        # Graceful fallback for new stages added after a user has saved config:
        # key_terms_extraction defaults to whatever article_synthesis uses.
        if stage_name == "key_terms_extraction" and "article_synthesis" in pipeline:
            return stage_config("article_synthesis")
        raise KeyError(
            f"ai_config.yaml 沒有 ai_pipeline.{stage_name} 區塊。"
            f"已知階段：{list(pipeline.keys())}"
        )
    sc = pipeline[stage_name]
    fb_data = sc.get("fallback")
    fallback = (
        StageConfig(
            provider=fb_data["provider"],
            model=fb_data["model"],
            temperature=sc["temperature"],
            max_tokens=sc["max_tokens"],
        )
        if fb_data
        else None
    )
    return StageConfig(
        provider=sc["provider"],
        model=sc["model"],
        temperature=sc["temperature"],
        max_tokens=sc["max_tokens"],
        fallback=fallback,
    )


def get_client_for_stage(stage_name: str) -> BaseLLMClient:
    """Return the primary client for a stage."""
    sc = stage_config(stage_name)
    return make_client(sc.provider, sc.model)


def get_fallback_client_for_stage(
    stage_name: str,
) -> BaseLLMClient | None:
    """Return the fallback client for a stage, or None.

    Returns None if no fallback configured OR the fallback's API key is missing
    (so the caller can degrade gracefully without crashing the whole pipeline).
    """
    sc = stage_config(stage_name)
    if not sc.fallback:
        return None
    try:
        return make_client(sc.fallback.provider, sc.fallback.model)
    except RuntimeError:
        # Missing API key for the fallback provider — treat as no fallback.
        return None


def global_setting(key: str, default: Any = None) -> Any:
    """Read a value from the `global:` section of ai_config.yaml."""
    cfg = load_config()
    return (cfg.get("global") or {}).get(key, default)


# =============================================================================
# JSON cleanup — LLMs love wrapping their output in fences and preambles.
# =============================================================================


_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def clean_json_response(text: str) -> str:
    """Strip common LLM noise around a JSON payload.

    Handles:
    - ```json ... ``` and ``` ... ``` markdown code fences
    - "Here is the JSON:" / "Sure! ..." preambles before the opening brace
    - Trailing prose after the closing brace
    """
    text = text.strip()
    if not text:
        return text

    fence = _FENCE_RE.search(text)
    if fence:
        text = fence.group(1).strip()

    # Find the first { or [ — anything before is preamble.
    open_idx = -1
    for ch in "{[":
        idx = text.find(ch)
        if idx != -1 and (open_idx == -1 or idx < open_idx):
            open_idx = idx
    if open_idx > 0:
        text = text[open_idx:]

    # Find the last } or ] — anything after is trailing junk.
    close_idx = max(text.rfind("}"), text.rfind("]"))
    if close_idx >= 0:
        text = text[: close_idx + 1]

    return text.strip()


def parse_json_response(text: str) -> Any:
    """Clean LLM output and run json.loads(). Raises json.JSONDecodeError on failure."""
    cleaned = clean_json_response(text)
    return json.loads(cleaned)


# =============================================================================
# Connection sanity check (used by `python -m scripts.llm_client --check ...`)
# =============================================================================


def _selftest_provider(provider: str, model: str) -> None:
    """Send the cheapest possible prompt to verify auth + connection."""
    print(f"→ 測試 {provider} ({model}) ...")
    client = make_client(provider, model)
    started = time.monotonic()
    resp = client.complete(
        prompt='Reply with this exact JSON and nothing else: {"ok": true}',
        temperature=0.0,
        max_tokens=50,
        response_format="json",
    )
    elapsed = time.monotonic() - started
    print(f"  ✓ 連線成功（{elapsed:.1f}s, {resp.tokens_used} tokens）")
    print(f"  原始回應：{resp.content[:200]}")
    try:
        parsed = parse_json_response(resp.content)
        print(f"  JSON 解析成功：{parsed}")
    except Exception as e:
        print(f"  ⚠️ JSON 解析失敗：{e}")


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="LLM client smoke test."
    )
    parser.add_argument(
        "--check",
        choices=list(_PROVIDERS.keys()),
        help="連線測試一個 provider。",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="指定 model（預設用 ai_config.yaml 第一個用到該 provider 的 model）。",
    )
    args = parser.parse_args()

    if args.check:
        # Pick a model: explicit --model, or scan ai_config.yaml for one.
        model = args.model
        if not model:
            cfg = load_config()
            for stage in (cfg.get("ai_pipeline") or {}).values():
                if stage.get("provider") == args.check:
                    model = stage["model"]
                    break
                fb = stage.get("fallback") or {}
                if fb.get("provider") == args.check:
                    model = fb["model"]
                    break
        if not model:
            # Last-resort defaults
            model = {
                "ollama": "qwen3.6:35b-a3b",
                "claude": "claude-sonnet-4-6",
                "gemini": "gemini-2.5-flash",
                "openrouter": "google/gemini-2.5-flash",
            }[args.check]
        try:
            _selftest_provider(args.check, model)
        except Exception as e:
            print(f"  ✗ 失敗：{e}")
            return 1
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
