# ArrakisEngine Roadmap

## Current Architecture

ArrakisEngine requires **reasoning models** for coaching analysis. Chess coaching
demands multi-step reasoning: evaluating positions, understanding strategic themes,
connecting patterns across games, and generating age-appropriate explanations.
Non-reasoning models produce shallow, generic feedback.

### Supported Providers

| Provider | Model | Type | Status |
|----------|-------|------|--------|
| Anthropic | `claude-opus-4-6` | Reasoning | **Active** |
| OpenAI | `chatgpt-5.4-pro` | Reasoning | **Active** |

---

## Planned: Ollama / Open-Source Models

### Goal
Enable fully local, offline coaching using open-source reasoning models via Ollama.
This removes API costs and latency, and enables privacy-first deployments.

### Requirements
- Model must support **chain-of-thought reasoning** — essential for:
  - Multi-move tactical analysis ("if Nxe5, then Qd4+ forces...")
  - Pattern recognition across game phases (opening prep → middlegame execution)
  - Connecting current game to historical coaching context (last 5 games)
  - Age-appropriate explanation generation (simplifying complex ideas)
- Model must handle **structured JSON output** reliably (coaching response format)
- Minimum context window: **16K tokens** (game PGN + move analysis + coaching history)

### Candidate Models (evaluate when available)
- **DeepSeek-R1** (32B+) — strong reasoning, Apache 2.0 license
- **Qwen3** reasoning variants — good multilingual support
- **Llama 4** reasoning variants — Meta's next-gen with extended context
- **Mistral** reasoning models — strong European alternative

### Implementation Plan
1. Add `ollama` as a third provider option alongside `claude` and `openai`
2. New `_call_ollama(prompt, model)` function in `src/coach.py`
3. Ollama model config in `config.yaml`:
   ```yaml
   coaching:
     ollama_model: deepseek-r1:32b    # or whichever reasoning model
     ollama_base_url: http://localhost:11434
   ```
4. UI: Add "Ollama" option to provider selector in Settings and pipeline panel
5. No API key needed — runs fully local
6. Benchmark: compare coaching quality against Claude/OpenAI baseline on same 20 games

### Challenges
- **Quality gap**: Open-source reasoning models may not match frontier model depth,
  especially for nuanced coaching tone adjustments (encouraging vs technical)
- **Speed**: Local inference on Apple Silicon (M-series) is viable but slower than API;
  32B models at ~15-20 tok/s on M3 Max, meaning ~60-90s per game coaching
- **Memory**: 32B models need ~20GB RAM; larger models need more
- **JSON reliability**: Smaller models may need output format enforcement or retry logic

### Non-Reasoning Models: Why They Don't Work
Models without chain-of-thought (e.g., standard chat models, small instruction-tuned
models) fail at chess coaching because they:
- Miss tactical sequences requiring look-ahead
- Generate generic advice not grounded in the actual position
- Cannot maintain coherent analysis across 30+ move games
- Produce inconsistent JSON structure

This is a hard requirement, not a preference.
