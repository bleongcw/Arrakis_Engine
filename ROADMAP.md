# ArrakisEngine Roadmap

## Current Architecture

ArrakisEngine requires **reasoning models** for coaching analysis. Chess coaching
demands multi-step reasoning: evaluating positions, understanding strategic themes,
connecting patterns across games, and generating age-appropriate explanations.
Non-reasoning models produce shallow, generic feedback.

### Supported Providers (8 total)

| Provider | Model | Type | Status |
|----------|-------|------|--------|
| Anthropic | `claude-opus-4-6` | Cloud / Reasoning | **Active** |
| OpenAI | `gpt-5.4-pro` | Cloud / Reasoning | **Active** |
| Google | `gemini-2.5-pro` | Cloud / Reasoning | **Active** |
| xAI | `grok-3` | Cloud / Reasoning | **Active** |
| Mistral | `mistral-medium-latest` | Cloud / Reasoning | **Active** |
| DeepSeek | `deepseek-reasoner` | Cloud / Reasoning | **Active** |
| Alibaba | `qwen3-235b-a22b` | Cloud / Reasoning | **Active** |
| Ollama | `deepseek-r1:8b` | Local / Reasoning | **Active** |

All providers are available in the CLI (`--provider`), the dashboard pipeline panel,
per-game coaching buttons, and the Settings page. The provider abstraction in
`src/llm_providers.py` makes adding new providers straightforward.

---

## Ollama / Local Models

### Current Support
Ollama is fully integrated as a local provider. It uses the OpenAI-compatible API
endpoint at `http://localhost:11434/v1` with no API key required.

**Default model:** `deepseek-r1:8b` (lightweight, ~5GB RAM, good for testing)

### Recommended Local Models (by capability)

| Model | Size | RAM | Quality | Speed (M3 Max) |
|-------|------|-----|---------|-----------------|
| `deepseek-r1:8b` | 8B | ~5GB | Good for testing | ~30 tok/s |
| `deepseek-r1:14b` | 14B | ~9GB | Moderate coaching | ~20 tok/s |
| `deepseek-r1:32b` | 32B | ~20GB | Strong coaching | ~15 tok/s |
| `qwen3:8b` | 8B | ~5GB | Good JSON reliability | ~30 tok/s |

### Challenges with Local Models
- **Quality gap**: Open-source reasoning models may not match frontier model depth,
  especially for nuanced coaching tone adjustments (encouraging vs technical)
- **Speed**: Local inference on Apple Silicon is viable but slower than API;
  32B models at ~15-20 tok/s on M3 Max, meaning ~60-90s per game coaching
- **Memory**: 32B models need ~20GB RAM; larger models need more
- **JSON reliability**: Smaller models may need retry logic for structured output

---

## Future Considerations

### Non-Reasoning Models: Why They Don't Work
Models without chain-of-thought (e.g., standard chat models, small instruction-tuned
models) fail at chess coaching because they:
- Miss tactical sequences requiring look-ahead
- Generate generic advice not grounded in the actual position
- Cannot maintain coherent analysis across 30+ move games
- Produce inconsistent JSON structure

This is a hard requirement, not a preference.

### Potential Future Providers
- Any OpenAI-compatible API can be added by registering in `src/llm_providers.py`
- Azure OpenAI, Together AI, Groq, Fireworks — all use the same SDK pattern
