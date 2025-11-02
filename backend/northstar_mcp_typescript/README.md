# Northstar MCP Server (TypeScript/Deno)

TypeScript/Deno implementation of the Northstar MCP Server for AI-powered experimentation using `@metorial/mcp-server-sdk`.

## Features

- **Propose Experiments**: Generate experiment proposals to improve product metrics
- **Execute Code Changes**: Use Morph Fast Apply to make code changes and create GitHub PRs

## Requirements

- [Deno](https://deno.com/) 1.40 or later
- Git (for repository operations)
- Environment variables (see below)
- `@metorial/mcp-server-sdk` package (installed automatically via Deno)

## Environment Variables

Set the following environment variables:

```bash
# Required for execute_code_change
TARGET_REPO=owner/repo          # Default repository (optional if provided in tool call)
TARGET_FILE=path/to/file        # Default file path (optional if provided in tool call)
GITHUB_TOKEN=your_github_token  # Required for creating PRs
MORPH_API_KEY=your_morph_key    # Required for Morph Fast Apply
MORPH_BASE_URL=https://api.morphllm.com/v1  # Optional, defaults to this value
```

## Installation

1. Install Deno if you haven't already:

```bash
curl -fsSL https://deno.land/install.sh | sh
```

2. Deno will automatically download dependencies from npm when you run the server. No `npm install` needed!

## Usage

Run the server:

```bash
deno task start
```

Or directly:

```bash
deno run --allow-env --allow-net --allow-read --allow-write --allow-run --allow-sys server.ts
```

The server runs on stdio and communicates via the Model Context Protocol (MCP) using the Metorial SDK.

## Development

Format code:

```bash
deno fmt
```

Lint code:

```bash
deno lint
```

## Project Structure

- `server.ts` - Main MCP server with tool definitions using `@metorial/mcp-server-sdk`
- `git_ops.ts` - Git operations (clone, branch, commit, push)
- `github_ops.ts` - GitHub API operations (create PR)
- `morph_client.ts` - Morph Fast Apply API client
- `utils.ts` - Utility functions (slugify, diff generation, PR formatting)
- `deno.json` - Deno configuration with npm imports
- `package.json` - Package metadata (for reference, Deno uses deno.json)
- `metorial.json` - Metorial runtime configuration

## Differences from Python Version

- Uses Deno's built-in APIs instead of Python libraries
- Uses `fetch()` for HTTP requests instead of `requests`
- Uses Deno subprocess commands for Git operations instead of GitPython
- Uses GitHub REST API directly instead of PyGithub
- Uses `@metorial/mcp-server-sdk` instead of `mcp` Python package
- Uses Zod schemas for input validation via the Metorial SDK

## Metorial SDK

This project uses `@metorial/mcp-server-sdk` which provides:
- Type-safe tool registration with Zod schemas
- Simplified server setup
- Automatic request handling
- Deno TypeScript runtime support

See `metorial.json` for runtime configuration.

