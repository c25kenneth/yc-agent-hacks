# Northstar Backend

FastAPI orchestrator + Northstar MCP Server

## Structure

```
backend/
├── main.py              # FastAPI orchestrator
├── northstar_mcp/       # Custom MCP server
│   ├── server.py       # MCP tool definitions
│   ├── morph_client.py # Morph API client
│   ├── git_ops.py      # Git automation
│   ├── github_ops.py   # PR creation
│   └── utils.py        # Utilities
└── pyproject.toml      # Dependencies
```

## Setup

```bash
uv sync
uvicorn main:app --reload
```

## API Endpoints

- `GET /oauth/start` - Start Slack OAuth
- `GET /oauth/complete` - Complete OAuth
- `POST /northstar/propose` - Generate proposal
- `POST /northstar/execute` - Execute experiment

## MCP Tools

### `propose_experiment()`
Returns experiment proposals

### `execute_code_change(instruction, update_block, repo, file_path)`
Executes code changes via Morph and creates GitHub PR
