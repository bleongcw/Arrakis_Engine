# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Unified LLM provider abstraction for ArrakisEngine.

Supports 8 providers: Claude, OpenAI, Gemini, Grok, Mistral, DeepSeek, Qwen, Ollama.
Each provider is registered with its SDK type, default model, API key env var,
and optional base URL. The `call_provider()` function dispatches to the correct SDK.
"""

import logging
import os
import re

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider Registry
# ---------------------------------------------------------------------------

PROVIDER_REGISTRY = {
    "claude": {
        "display_name": "Claude",
        "sdk_type": "anthropic",
        "default_model": "claude-opus-4-7",
        "env_var": "ARRAKIS_ANTHROPIC_API_KEY",
        "base_url": None,
        "default_timeout": 300.0,  # Opus with extended thinking needs more time
        "config_model_key": "anthropic_model",
        "group": "cloud",
        "color": "#7c3aed",
    },
    "openai": {
        "display_name": "ChatGPT",
        "sdk_type": "openai_responses",
        "default_model": "gpt-5.5-pro-2026-04-23",
        "env_var": "ARRAKIS_OPENAI_API_KEY",
        "base_url": None,
        "default_timeout": 120.0,
        "config_model_key": "openai_model",
        "group": "cloud",
        "color": "#059669",
    },
    "gemini": {
        "display_name": "Gemini",
        "sdk_type": "google_genai",
        "default_model": "gemini-2.5-pro",
        "env_var": "ARRAKIS_GOOGLE_API_KEY",
        "base_url": None,
        "default_timeout": 300.0,  # Reasoning model, needs more time
        "config_model_key": "gemini_model",
        "group": "cloud",
        "color": "#4285f4",
    },
    "grok": {
        "display_name": "Grok",
        "sdk_type": "openai_chat",
        "default_model": "grok-3",
        "env_var": "ARRAKIS_XAI_API_KEY",
        "base_url": "https://api.x.ai/v1",
        "default_timeout": 120.0,
        "config_model_key": "grok_model",
        "group": "cloud",
        "color": "#1d9bf0",
    },
    "mistral": {
        "display_name": "Mistral",
        "sdk_type": "mistral",
        "default_model": "mistral-medium-latest",
        "env_var": "ARRAKIS_MISTRAL_API_KEY",
        "base_url": None,
        "default_timeout": 120.0,
        "config_model_key": "mistral_model",
        "group": "cloud",
        "color": "#f97316",
    },
    "deepseek": {
        "display_name": "DeepSeek",
        "sdk_type": "openai_chat",
        "default_model": "deepseek-reasoner",
        "env_var": "ARRAKIS_DEEPSEEK_API_KEY",
        "base_url": "https://api.deepseek.com",
        "default_timeout": 300.0,  # Reasoning model, needs more time
        "config_model_key": "deepseek_model",
        "group": "cloud",
        "color": "#6366f1",
    },
    "qwen": {
        "display_name": "Qwen",
        "sdk_type": "openai_chat",
        "default_model": "qwen3-235b-a22b",
        "env_var": "ARRAKIS_QWEN_API_KEY",
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "default_timeout": 120.0,
        "config_model_key": "qwen_model",
        "group": "cloud",
        "color": "#ef4444",
    },
    "ollama": {
        "display_name": "Ollama (Local)",
        "sdk_type": "openai_chat",
        "default_model": "deepseek-r1:8b",
        "env_var": None,  # No API key needed
        "base_url": "http://localhost:11434/v1",
        "default_timeout": 300.0,  # Local models are slower
        "config_model_key": "ollama_model",
        "group": "local",
        "color": "#737373",
    },
}

# All valid provider slugs
VALID_PROVIDERS = set(PROVIDER_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Thinking tag stripping (for reasoning models like DeepSeek-R1, Qwen3)
# ---------------------------------------------------------------------------

_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_thinking_tags(text: str) -> str:
    """Remove <think>...</think> blocks from reasoning model output."""
    return _THINK_PATTERN.sub("", text).strip()


# ---------------------------------------------------------------------------
# SDK Call Implementations
# ---------------------------------------------------------------------------

def _call_anthropic(prompt: str, model: str, api_key: str,
                    timeout: float = 120.0) -> str:
    """Call Anthropic Claude API with extended thinking."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)

    response = client.messages.create(
        model=model,
        max_tokens=16000,
        thinking={
            "type": "adaptive",
        },
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text from response (skip thinking blocks)
    for block in response.content:
        if block.type == "text":
            return block.text

    raise ValueError("No text content in Claude response")


def _call_openai_responses(prompt: str, model: str, api_key: str,
                           timeout: float = 120.0) -> str:
    """Call OpenAI Responses API (for ChatGPT reasoning models)."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=timeout)

    response = client.responses.create(
        model=model,
        instructions="You are an expert chess coach. Respond only with valid JSON.",
        input=prompt,
    )

    return response.output_text


def _call_openai_chat(prompt: str, model: str, api_key: str | None,
                      base_url: str, timeout: float = 120.0) -> str:
    """Call OpenAI-compatible chat completions API.

    Used for: xAI Grok, DeepSeek, Qwen, Ollama.
    """
    from openai import OpenAI

    client_kwargs = {"base_url": base_url, "timeout": timeout}
    if api_key:
        client_kwargs["api_key"] = api_key
    else:
        # Ollama doesn't need an API key but the SDK requires something
        client_kwargs["api_key"] = "ollama"

    client = OpenAI(**client_kwargs)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system",
             "content": "You are an expert chess coach. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )

    text = response.choices[0].message.content or ""
    return _strip_thinking_tags(text)


def _call_google_genai(prompt: str, model: str, api_key: str,
                       timeout: float = 120.0) -> str:
    """Call Google Gemini via google-genai SDK."""
    from google import genai

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
    )

    return response.text or ""


def _call_mistral(prompt: str, model: str, api_key: str,
                  timeout: float = 120.0) -> str:
    """Call Mistral AI API."""
    from mistralai import Mistral

    client = Mistral(api_key=api_key, timeout_ms=int(timeout * 1000))

    response = client.chat.complete(
        model=model,
        messages=[
            {"role": "system",
             "content": "You are an expert chess coach. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_model(provider_slug: str, explicit_model: str | None,
                  coaching_config: dict | None = None) -> str:
    """Resolve the model to use for a provider.

    Priority: explicit_model > config value > registry default.
    """
    if provider_slug not in PROVIDER_REGISTRY:
        raise ValueError(f"Unknown provider: {provider_slug}")

    if explicit_model:
        return explicit_model

    reg = PROVIDER_REGISTRY[provider_slug]

    if coaching_config:
        config_model = coaching_config.get(reg["config_model_key"])
        if config_model:
            return config_model

    return reg["default_model"]


def call_provider(provider_slug: str, prompt: str,
                  model: str | None = None, timeout: float | None = None,
                  coaching_config: dict | None = None) -> str:
    """Call an LLM provider and return the response text.

    Args:
        provider_slug: Provider identifier (e.g., "claude", "ollama").
        prompt: The full prompt to send.
        model: Optional model override. If None, uses config or default.
        timeout: Optional timeout override in seconds.
        coaching_config: The coaching section of config.yaml for model resolution.

    Returns:
        Raw text response from the LLM.

    Raises:
        ValueError: If provider is unknown or API key is missing.
        ConnectionError: If Ollama is not running.
    """
    if provider_slug not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown provider: {provider_slug}. "
            f"Valid providers: {', '.join(sorted(VALID_PROVIDERS))}"
        )

    reg = PROVIDER_REGISTRY[provider_slug]
    sdk_type = reg["sdk_type"]
    used_model = resolve_model(provider_slug, model, coaching_config)
    used_timeout = timeout or reg["default_timeout"]

    # Validate API key (skip for Ollama)
    api_key = None
    if reg["env_var"]:
        api_key = os.getenv(reg["env_var"])
        if not api_key:
            raise ValueError(
                f"{reg['env_var']} not set in environment. "
                f"Required for {reg['display_name']} provider."
            )

    logger.info("Calling %s with model %s...", reg["display_name"], used_model)

    try:
        if sdk_type == "anthropic":
            return _call_anthropic(prompt, used_model, api_key, used_timeout)

        elif sdk_type == "openai_responses":
            return _call_openai_responses(prompt, used_model, api_key, used_timeout)

        elif sdk_type == "openai_chat":
            base_url = reg["base_url"]
            # Allow config override for Ollama base URL
            if provider_slug == "ollama" and coaching_config:
                base_url = coaching_config.get("ollama_base_url", base_url)
            return _call_openai_chat(
                prompt, used_model, api_key, base_url, used_timeout
            )

        elif sdk_type == "google_genai":
            return _call_google_genai(prompt, used_model, api_key, used_timeout)

        elif sdk_type == "mistral":
            return _call_mistral(prompt, used_model, api_key, used_timeout)

        else:
            raise ValueError(f"Unknown SDK type: {sdk_type}")

    except ConnectionError:
        if provider_slug == "ollama":
            raise ConnectionError(
                "Cannot connect to Ollama. Is it running? "
                "Start it with: ollama serve"
            ) from None
        raise
    except Exception as e:
        # Re-raise with provider context for better error messages
        if "Connection" in type(e).__name__ and provider_slug == "ollama":
            raise ConnectionError(
                "Cannot connect to Ollama at "
                f"{reg['base_url']}. "
                "Start it with: ollama serve"
            ) from e
        raise


def get_available_providers(coaching_config: dict | None = None) -> list[dict]:
    """Return list of all providers with their configuration status.

    Each entry includes: slug, display_name, group, color, configured (bool),
    model (resolved model name).
    """
    result = []
    for slug, reg in PROVIDER_REGISTRY.items():
        configured = True
        if reg["env_var"]:
            configured = bool(os.getenv(reg["env_var"]))
        elif slug == "ollama":
            # Ollama is always "configured" but may not be running
            configured = True

        model = resolve_model(slug, None, coaching_config)

        result.append({
            "slug": slug,
            "display_name": reg["display_name"],
            "group": reg["group"],
            "color": reg["color"],
            "configured": configured,
            "model": model,
            "env_var": reg["env_var"],
        })

    return result
