# ArrakisEngine — Chess Coaching AI
# Copyright (C) 2026 Bernard Leong
# Licensed under AGPL-3.0. See LICENSE file.

"""Tests for unified LLM provider abstraction."""

import os
from unittest.mock import patch, MagicMock

import pytest

from src.llm_providers import (
    PROVIDER_REGISTRY,
    VALID_PROVIDERS,
    _strip_thinking_tags,
    _effort_for,
    _call_anthropic,
    _call_openai_responses,
    resolve_model,
    call_provider,
    get_available_providers,
)


# ── Registry ─────────────────────────────────────────────


class TestProviderRegistry:
    """Verify the provider registry is complete and well-formed."""

    REQUIRED_KEYS = {
        "display_name", "sdk_type", "default_model", "env_var",
        "base_url", "default_timeout", "config_model_key", "group", "color",
    }

    def test_has_all_eight_providers(self):
        expected = {"claude", "openai", "gemini", "grok", "mistral", "deepseek", "qwen", "ollama"}
        assert set(PROVIDER_REGISTRY.keys()) == expected

    def test_valid_providers_matches_registry(self):
        assert VALID_PROVIDERS == set(PROVIDER_REGISTRY.keys())

    @pytest.mark.parametrize("slug", list(PROVIDER_REGISTRY.keys()))
    def test_provider_has_required_keys(self, slug):
        entry = PROVIDER_REGISTRY[slug]
        missing = self.REQUIRED_KEYS - set(entry.keys())
        assert not missing, f"{slug} missing keys: {missing}"

    def test_ollama_has_no_env_var(self):
        assert PROVIDER_REGISTRY["ollama"]["env_var"] is None

    def test_cloud_providers_have_env_vars(self):
        cloud = [s for s, r in PROVIDER_REGISTRY.items() if r["group"] == "cloud"]
        for slug in cloud:
            assert PROVIDER_REGISTRY[slug]["env_var"] is not None, f"{slug} missing env_var"

    @pytest.mark.parametrize("slug", list(PROVIDER_REGISTRY.keys()))
    def test_timeout_is_positive(self, slug):
        assert PROVIDER_REGISTRY[slug]["default_timeout"] > 0

    def test_openai_timeout_at_least_600s(self):
        # v1.8.1 regression lock: gpt-5.6-sol is a deep-reasoning model and the
        # ~6200-token coaching prompt (history + trajectory injection) regularly
        # takes 2-5 minutes end-to-end. Live verification on Bernard's DB clocked
        # 5min02s on Evan's game 954. The 300s floor matches Claude/DeepSeek/Gemini
        # but is still too tight in practice — 600s gives real headroom.
        assert PROVIDER_REGISTRY["openai"]["default_timeout"] >= 600.0


# ── Thinking tag stripping ───────────────────────────────


class TestStripThinkingTags:
    """Verify <think> block removal for reasoning models."""

    def test_strips_simple_think_block(self):
        text = '<think>internal reasoning</think>{"key": "value"}'
        assert _strip_thinking_tags(text) == '{"key": "value"}'

    def test_strips_multiline_think_block(self):
        text = '<think>\nline1\nline2\n</think>\n{"result": true}'
        assert _strip_thinking_tags(text).startswith('{"result"')

    def test_preserves_text_without_think_tags(self):
        text = '{"key": "value"}'
        assert _strip_thinking_tags(text) == text

    def test_strips_multiple_think_blocks(self):
        text = '<think>a</think>hello<think>b</think>world'
        assert _strip_thinking_tags(text) == "helloworld"

    def test_handles_empty_think_block(self):
        text = '<think></think>{"ok": true}'
        assert _strip_thinking_tags(text) == '{"ok": true}'

    def test_handles_empty_string(self):
        assert _strip_thinking_tags("") == ""


# ── Model resolution ────────────────────────────────────


class TestResolveModel:
    """Verify model resolution priority: explicit > config > default."""

    def test_explicit_model_wins(self):
        result = resolve_model("claude", "my-custom-model")
        assert result == "my-custom-model"

    def test_config_model_wins_over_default(self):
        config = {"anthropic_model": "claude-sonnet-4-5-20250514"}
        result = resolve_model("claude", None, config)
        assert result == "claude-sonnet-4-5-20250514"

    def test_default_model_used_when_no_config(self):
        result = resolve_model("claude", None, None)
        assert result == "claude-opus-4-8"

    def test_default_model_used_when_config_key_missing(self):
        result = resolve_model("claude", None, {"openai_model": "gpt-5.6-sol"})
        assert result == "claude-opus-4-8"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            resolve_model("nonexistent", None)

    @pytest.mark.parametrize("slug", list(PROVIDER_REGISTRY.keys()))
    def test_all_providers_resolve_default(self, slug):
        result = resolve_model(slug, None, None)
        assert result == PROVIDER_REGISTRY[slug]["default_model"]


# ── call_provider dispatch ──────────────────────────────


class TestCallProvider:
    """Verify call_provider dispatches correctly and validates inputs."""

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            call_provider("nonexistent", "prompt")

    @patch.dict(os.environ, {}, clear=False)
    def test_missing_api_key_raises(self):
        # Ensure the key is NOT set
        os.environ.pop("ARRAKIS_ANTHROPIC_API_KEY", None)
        with pytest.raises(ValueError, match="not set"):
            call_provider("claude", "prompt")

    @patch("src.llm_providers._call_anthropic")
    @patch.dict(os.environ, {"ARRAKIS_ANTHROPIC_API_KEY": "test-key"})
    def test_dispatches_to_anthropic(self, mock_call):
        mock_call.return_value = '{"result": "ok"}'
        result = call_provider("claude", "prompt")
        assert result == '{"result": "ok"}'
        mock_call.assert_called_once()

    @patch("src.llm_providers._call_openai_responses")
    @patch.dict(os.environ, {"ARRAKIS_OPENAI_API_KEY": "test-key"})
    def test_dispatches_to_openai_responses(self, mock_call):
        mock_call.return_value = '{"result": "ok"}'
        result = call_provider("openai", "prompt")
        assert result == '{"result": "ok"}'
        mock_call.assert_called_once()

    @patch("src.llm_providers._call_openai_chat")
    @patch.dict(os.environ, {"ARRAKIS_XAI_API_KEY": "test-key"})
    def test_dispatches_to_openai_chat_for_grok(self, mock_call):
        mock_call.return_value = '{"result": "ok"}'
        result = call_provider("grok", "prompt")
        assert result == '{"result": "ok"}'
        mock_call.assert_called_once()

    @patch("src.llm_providers._call_openai_chat")
    def test_ollama_needs_no_api_key(self, mock_call):
        mock_call.return_value = '{"result": "ok"}'
        result = call_provider("ollama", "prompt")
        assert result == '{"result": "ok"}'
        mock_call.assert_called_once()

    @patch("src.llm_providers._call_google_genai")
    @patch.dict(os.environ, {"ARRAKIS_GOOGLE_API_KEY": "test-key"})
    def test_dispatches_to_google_genai(self, mock_call):
        mock_call.return_value = '{"result": "ok"}'
        result = call_provider("gemini", "prompt")
        assert result == '{"result": "ok"}'
        mock_call.assert_called_once()

    @patch("src.llm_providers._call_mistral")
    @patch.dict(os.environ, {"ARRAKIS_MISTRAL_API_KEY": "test-key"})
    def test_dispatches_to_mistral(self, mock_call):
        mock_call.return_value = '{"result": "ok"}'
        result = call_provider("mistral", "prompt")
        assert result == '{"result": "ok"}'
        mock_call.assert_called_once()


# ── get_available_providers ─────────────────────────────


class TestGetAvailableProviders:
    """Verify provider availability listing."""

    def test_returns_all_eight_providers(self):
        providers = get_available_providers()
        assert len(providers) == 8

    def test_each_provider_has_required_fields(self):
        providers = get_available_providers()
        required = {"slug", "display_name", "group", "color", "configured", "model", "env_var"}
        for p in providers:
            missing = required - set(p.keys())
            assert not missing, f"{p['slug']} missing fields: {missing}"

    @patch.dict(os.environ, {"ARRAKIS_ANTHROPIC_API_KEY": "test"}, clear=False)
    def test_configured_when_key_present(self):
        providers = get_available_providers()
        claude = next(p for p in providers if p["slug"] == "claude")
        assert claude["configured"] is True

    @patch.dict(os.environ, {}, clear=False)
    def test_not_configured_when_key_absent(self):
        os.environ.pop("ARRAKIS_ANTHROPIC_API_KEY", None)
        providers = get_available_providers()
        claude = next(p for p in providers if p["slug"] == "claude")
        assert claude["configured"] is False

    def test_ollama_always_configured(self):
        providers = get_available_providers()
        ollama = next(p for p in providers if p["slug"] == "ollama")
        assert ollama["configured"] is True


# ── Reasoning effort (v1.27.0) ───────────────────────────


class TestReasoningEffort:
    """Configurable reasoning effort: clamp per provider + reaches the SDK call."""

    @pytest.mark.parametrize("provider,effort,expected", [
        ("claude", "xhigh", "xhigh"),
        ("claude", "max", "max"),
        ("claude", "low", "low"),
        ("openai", "xhigh", "xhigh"),
        ("openai", "max", "xhigh"),        # OpenAI scale tops out at xhigh
        ("mistral", "xhigh", "high"),      # Mistral caps at high
        ("mistral", "max", "high"),
        ("mistral", "medium", "medium"),
        ("grok", "xhigh", None),           # no compatible knob
        ("gemini", "xhigh", None),
        ("deepseek", "xhigh", None),
        ("qwen", "xhigh", None),
        ("ollama", "xhigh", None),
        ("claude", None, None),
        ("claude", "", None),
    ])
    def test_effort_for_clamps(self, provider, effort, expected):
        assert _effort_for(provider, effort) == expected

    def _fake_anthropic(self):
        client = MagicMock()
        block = MagicMock()
        block.type = "text"
        block.text = "ok"
        client.messages.create.return_value.content = [block]
        return client

    def test_anthropic_passes_output_config_effort(self):
        client = self._fake_anthropic()
        with patch("anthropic.Anthropic", return_value=client):
            _call_anthropic("prompt", "claude-opus-4-8", "key", effort="xhigh")
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["output_config"] == {"effort": "xhigh"}
        assert kwargs["thinking"] == {"type": "adaptive"}  # kept

    def test_anthropic_omits_output_config_when_no_effort(self):
        client = self._fake_anthropic()
        with patch("anthropic.Anthropic", return_value=client):
            _call_anthropic("prompt", "claude-opus-4-8", "key", effort=None)
        assert "output_config" not in client.messages.create.call_args.kwargs

    def test_openai_responses_passes_reasoning_effort(self):
        client = MagicMock()
        client.responses.create.return_value.output_text = "ok"
        with patch("openai.OpenAI", return_value=client):
            _call_openai_responses("prompt", "gpt-5.6-sol", "key", effort="xhigh")
        assert client.responses.create.call_args.kwargs["reasoning"] == {"effort": "xhigh"}

    def test_call_provider_claude_applies_config_effort(self):
        """End-to-end dispatch: coaching_config.reasoning_effort reaches the call."""
        client = self._fake_anthropic()
        with patch("anthropic.Anthropic", return_value=client), \
             patch.dict(os.environ, {"ARRAKIS_ANTHROPIC_API_KEY": "k"}):
            call_provider("claude", "prompt",
                          coaching_config={"reasoning_effort": "max"})
        assert client.messages.create.call_args.kwargs["output_config"] == {"effort": "max"}

    def test_call_provider_default_effort_is_xhigh(self):
        """No reasoning_effort in config → defaults to xhigh."""
        client = self._fake_anthropic()
        with patch("anthropic.Anthropic", return_value=client), \
             patch.dict(os.environ, {"ARRAKIS_ANTHROPIC_API_KEY": "k"}):
            call_provider("claude", "prompt", coaching_config={})
        assert client.messages.create.call_args.kwargs["output_config"] == {"effort": "xhigh"}
