<p align="center">
  <img src="./frontend/src/assets/Header.png"alt="Northstar Wordmark">
</p>

# Northstar

Your autonomous teammate in Slack that proposes experiments and ships code.

Northstar exists because product iteration has become the new bottleneck, and AI can now close the loop between insight, code, and impact.

## What it does

```
You: "northstar, how are our DAUs looking?"
Northstar: "DAUs at 2,847 users, up 18% from last week.
           Mobile engagement increased 31% after navigation improvements."

You: "propose an experiment to improve retention"
Northstar: [Analyzes codebase, proposes experiment with confidence scores]

You: "make it happen"
Northstar: "PR #47 is up. This should improve perceived performance
           without touching backend."

You: "nice work"
Northstar: "Merged successfully. Monitoring retention impact."
```

Northstar analyzes your product data, understands your codebase, proposes changes, and opens PRs. All from Slack.

## System Overview

Northstar uses a two-stage system to keep latency under 1 second for most queries:

**Stage 1: Intent Detection** (200ms)
```python
# Fast classification determines which tools are needed
CASUAL_CHAT       → Slack only
REPO_ANALYSIS     → Captain knowledge base + Slack
ANALYTICS_QUERY   → PostHog + Slack
CODE_CHANGE       → GitHub + Northstar MCP + Slack
EXPERIMENT_PROPOSAL → All tools
```

**Stage 2: Execute**
```
Only loads the MCP servers needed for this specific request
├─ Slack MCP (OAuth-enabled)
├─ GitHub MCP (PR creation)
├─ PostHog MCP (analytics)
└─ Northstar MCP (custom experiment tools)
```

The triage pattern means simple queries don't pay the cost of loading unused tools.

### Stack

```
Slack Events API
    ↓
FastAPI + Background Tasks
    ↓
Metorial MCP Orchestration (GPT-4o)
    ↓
    ├─ Slack MCP
    ├─ GitHub MCP
    ├─ PostHog MCP
    └─ Custom Northstar MCP → Morph API (code generation)
```

Data layer: Supabase for experiment tracking and state.

Knowledge layer: Captain for codebase indexing (unbounded context windows).

## Setup

**Prerequisites:** Python 3.12+, Node.js 18+, UV package manager

**Backend:**
```bash
cd backend
uv sync
cp .env.example .env  # Add API keys
uvicorn main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
cp .env.example .env  # Add Supabase credentials
npm run dev
```

**Database:** Create Supabase project, run schema from `backend/SUPABASE_SCHEMA.md`

Connect a GitHub repo through the frontend at `localhost:5173`, then start messaging in Slack.

## Implementation notes

- 2,616 lines in `main.py` (core orchestrator)
- Type-safe with comprehensive hints throughout
- Async-first with FastAPI background tasks
- Agent personality system makes responses feel like a calm engineer, not a chatbot
- Rich Slack markdown formatting (no blocks, just clean text)

The triage system was the key architectural choice. Loading all MCP servers upfront added 3-5s latency even for "hey northstar" queries. Now simple messages respond in under a second.

## What's next

- Making integration take 10 minutes --> < 1 minute
- Getting 3–5 pilot teams — [Talk to us if you're interested](https://tally.so/r/worWMX)
- Iterating based on customer feedback
- Applying to YC W26

## Built with

[Metorial](https://metorial.com), [Morph](https://morphllm.com), [Captain](https://runcaptain.com), [PostHog](https://posthog.com), [Supabase](https://supabase.com), FastAPI, React, TailwindCSS

---

Originally Built for YC Agent Jam, November 2025
