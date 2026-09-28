# Bob Terminal 🤖

A terminal chat interface that connects to any OpenAI-compatible LLM and shows
live token burn + cost tracking in a rich dashboard.

## Features

- Works with OpenAI, watsonx.ai, Ollama, LM Studio, or any OpenAI-compatible API
- Live token burn meter that fills as tokens accumulate
- Per-prompt and session-total cost tracking (USD)
- Conversation history kept in-session (multi-turn context)
- Clean Rich-powered UI with coloured panels and spinner

## Setup

```bash
cd bob-terminal
pip install -r requirements.txt
cp .env.template .env          # then edit .env with your values
```

Edit `.env`:

```
API_BASE=https://api.openai.com/v1
API_KEY=sk-...
MODEL=gpt-4o-mini
MAX_TOKENS=1024
COST_PER_1K_PROMPT=0.01        # optional, USD
COST_PER_1K_COMPLETION=0.03    # optional, USD
```

## Usage

```bash
python bob_terminal.py
```

Type a message and press **Enter**. Type `exit` or `quit` to leave.

## Token Burn Dashboard

After every reply you'll see a panel like:

```
┌──────────────────── 🔥 TOKEN BURN ────────────────────┐
│ Burn       [████████░░░░░░░░░░░░░░░░░░░░░░] 27%        │
│ Session    2,700 tokens                                 │
│ Cost       $0.0539 USD                                  │
│ Last msg   340p / 120c = 460 total                      │
│ Breakdown  Prompt: 2,100  |  Completion: 600            │
│ Turns      4                                            │
└────────────────────────────────────────────────────────┘
```

The bar turns yellow at 50 % and red at 80 % of the 10 000-token session cap.
