# AI Integration Guide

## Modes

| Mode       | Behaviour                                                   |
|------------|-------------------------------------------------------------|
| `off`      | No AI analysis. DE score alone determines decision.         |
| `advisory` | AI analyzes signal; result shown in UI but doesn't block.   |
| `override` | AI can upgrade SKIP→TAKE or downgrade TAKE→SKIP.            |
| `required` | Signal rejected if AI provider unavailable.                  |

## Providers

### Claude (Anthropic)
- Model: `claude-sonnet-4-5` (default)
- Context: market snapshot, indicator values, signal details, recent history
- Output format: `{ decision, confidence, reasoning, key_factors }`

### OpenAI (GPT-4o)
- Model: `gpt-4o-mini` (configurable)
- Same prompt format as Claude

### Ollama (local)
- Default model: `deepseek-r1:8b`
- Runs locally — no API key required
- Slower but private

## Prompt Structure

```
System: You are an expert MOEX equity trader. Analyze the signal and respond in JSON only.

User:
Signal: {side} {instrument_id} @ {entry}
SL: {sl} | TP: {tp} | R/R: {r:.2f}
DE Score: {score}/100

Market context:
- RSI(14): {rsi:.1f}
- EMA50: {ema50:.2f} | Price vs EMA: {pct:+.1f}%
- ATR(14): {atr:.2f}
- Volume ratio: {vol_ratio:.2f}x

Respond ONLY with JSON:
{
  "decision": "TAKE" | "SKIP" | "REJECT",
  "confidence": 0.0-1.0,
  "reasoning": "...",
  "key_factors": ["...", "..."]
}
```

## AI Decision Outcome Tracking

After position close, `ai_repo.update_outcome(signal_id, outcome)` records:
- `profit` — closed above entry (TP hit or manual close in profit)
- `loss` — closed below entry (SL hit)
- `stopped` — time stop or session end

This data feeds the **AI win rate** metric shown in AI Settings panel.

## Configuration (AISettingsPanel)

```python
# Settings model fields
ai_mode:            str  # off / advisory / override / required
ai_provider:        str  # claude / openai / ollama / skip
ai_min_confidence:  int  # 50–95 (minimum confidence to override DE)
claude_api_key:     str  # encrypted in DB
openai_api_key:     str
ollama_base_url:    str  # default: http://localhost:11434
ollama_model:       str  # default: deepseek-r1:8b
```
