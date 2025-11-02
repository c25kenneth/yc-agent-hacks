# Northstar

Autonomous AI agent that proposes, executes, and learns from product experiments.

## Overview

Northstar uses Metorial's MCP protocol to orchestrate AI-powered code changes via Morph, creating real GitHub PRs for human review.

**Key Features:**
- AI-generated experiment proposals
- Automated code editing with Morph Fast Apply
- Real GitHub PR creation
- Slack integration for approvals

## Architecture

```
Slack/API → FastAPI → Metorial (AI Orchestrator)
                         ↓
              ┌──────────┼──────────┐
              ↓          ↓          ↓
         Northstar   GitHub     Slack
         MCP Tools   MCP        MCP
              ↓
         Morph API
```

## Quick Start

### Backend

```bash
cd backend
uv sync
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Environment Setup

Copy `backend/.env.example` to `backend/.env` and configure:

```bash
METORIAL_API_KEY=your_key
SLACK_DEPLOYMENT_ID=your_deployment
GITHUB_TOKEN=your_token
MORPH_API_KEY=your_key
TARGET_REPO=owner/repo
TARGET_FILE=index.html
```

## Tech Stack

- **Backend:** FastAPI, Metorial SDK, Morph API, GitPython, PyGithub
- **Frontend:** React 19, Vite 7, TailwindCSS 4
- **AI:** OpenAI GPT-4o, Metorial MCP Protocol

## License

MIT
