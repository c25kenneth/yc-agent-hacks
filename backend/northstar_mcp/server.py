"""Northstar MCP Server - Custom tools for AI-powered experimentation."""

import os
from pathlib import Path
from git import Repo
from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

from .morph_client import merge_code, MorphAPIError
from .git_ops import clone_repo, ensure_branch, create_commit_and_push, cleanup_repo
from .github_ops import open_pr
from .utils import slugify, unified_diff, format_pr_body


# Initialize MCP server
server = Server("northstar-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for the Northstar agent."""
    return [
        Tool(
            name="propose_experiment",
            description="Generate an experiment proposal to improve product metrics",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="execute_code_change",
            description="Execute a code change using Morph Fast Apply and create a GitHub PR",
            inputSchema={
                "type": "object",
                "properties": {
                    "instruction": {
                        "type": "string",
                        "description": "Natural language description of the code change"
                    },
                    "update_block": {
                        "type": "string",
                        "description": "Fast Apply format code snippet with '// ... existing code ...' markers"
                    },
                    "repo": {
                        "type": "string",
                        "description": "Repository name in format 'owner/repo' (optional, uses env default)"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to file to modify (optional, uses env default)"
                    },
                    "base_branch": {
                        "type": "string",
                        "description": "Base branch to merge into (default: main)"
                    }
                },
                "required": ["instruction", "update_block"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from the AI agent."""

    if name == "propose_experiment":
        return await propose_experiment()

    elif name == "execute_code_change":
        return await execute_code_change(
            instruction=arguments["instruction"],
            update_block=arguments["update_block"],
            repo=arguments.get("repo"),
            file_path=arguments.get("file_path"),
            base_branch=arguments.get("base_branch", "main")
        )

    else:
        raise ValueError(f"Unknown tool: {name}")


async def propose_experiment() -> list[TextContent]:
    """
    Generate a hardcoded experiment proposal.

    Returns:
        List containing experiment proposal as JSON
    """
    # Hardcoded proposals for MVP demo
    proposals = [
        {
            "proposal_id": "exp-001",
            "idea_summary": "Simplify checkout form by reducing fields from 8 to 4",
            "rationale": "Competitor analysis shows that simpler checkout flows improve conversion. Removing optional fields reduces friction.",
            "expected_impact": {
                "metric": "checkout_conversion",
                "delta_pct": 0.048
            },
            "technical_plan": [
                {
                    "file": "checkout.html",
                    "action": "Remove optional address fields and combine name fields"
                }
            ],
            "category": "checkout_optimization",
            "confidence": 0.75
        },
        {
            "proposal_id": "exp-002",
            "idea_summary": "Add trust badges below payment button",
            "rationale": "Security concerns are a top barrier to conversion. Trust badges from SSL provider can increase confidence.",
            "expected_impact": {
                "metric": "checkout_conversion",
                "delta_pct": 0.032
            },
            "technical_plan": [
                {
                    "file": "checkout.html",
                    "action": "Add SSL badge and money-back guarantee icon below CTA"
                }
            ],
            "category": "trust_building",
            "confidence": 0.68
        },
        {
            "proposal_id": "exp-003",
            "idea_summary": "Optimize button color for higher visibility",
            "rationale": "Current button (#3b82f6) has low contrast ratio. Increasing to high-contrast green can improve click rate.",
            "expected_impact": {
                "metric": "cta_click_rate",
                "delta_pct": 0.056
            },
            "technical_plan": [
                {
                    "file": "styles.css",
                    "action": "Change primary button color from blue to high-contrast green (#10b981)"
                }
            ],
            "category": "ui_optimization",
            "confidence": 0.62
        }
    ]

    # Return first proposal for demo
    import json
    proposal = proposals[0]

    return [TextContent(
        type="text",
        text=json.dumps(proposal, indent=2)
    )]


async def execute_code_change(
    instruction: str,
    update_block: str,
    repo: str | None = None,
    file_path: str | None = None,
    base_branch: str = "main"
) -> list[TextContent]:
    """
    Execute a code change using Morph Fast Apply and create a GitHub PR.

    Args:
        instruction: Natural language description of the change
        update_block: Fast Apply format code snippet
        repo: Repository name (owner/repo) - uses TARGET_REPO env if not provided
        file_path: Path to file to modify - uses TARGET_FILE env if not provided
        base_branch: Base branch to merge into (default: main)

    Returns:
        List containing PR URL and execution details
    """
    # Use env vars as defaults
    target_repo = repo or os.getenv("TARGET_REPO")
    target_file = file_path or os.getenv("TARGET_FILE")

    if not target_repo:
        return [TextContent(
            type="text",
            text="Error: TARGET_REPO not set in environment and not provided as argument"
        )]

    if not target_file:
        return [TextContent(
            type="text",
            text="Error: TARGET_FILE not set in environment and not provided as argument"
        )]

    repo_path = None
    try:
        # Clone repository
        repo_path = clone_repo(target_repo)

        # Read current file
        file_full_path = repo_path / target_file
        if not file_full_path.exists():
            return [TextContent(
                type="text",
                text=f"Error: File {target_file} not found in repository"
            )]

        current_content = file_full_path.read_text(encoding='utf-8')

        # Call Morph API to merge code
        try:
            merged_content = merge_code(instruction, current_content, update_block)
        except MorphAPIError as e:
            return [TextContent(
                type="text",
                text=f"Morph API Error: {str(e)}"
            )]

        # Generate diff
        diff = unified_diff(current_content, merged_content, target_file)

        if not diff:
            return [TextContent(
                type="text",
                text="No changes detected - merged code is identical to original"
            )]

        # Write merged content
        file_full_path.write_text(merged_content, encoding='utf-8')

        # Git operations
        git_repo = Repo(repo_path)
        branch_slug = slugify(instruction)
        branch_name = f"northstar/{branch_slug}"
        final_branch = ensure_branch(git_repo, base_branch, branch_name)

        commit_message = f"Northstar: {instruction}"
        create_commit_and_push(git_repo, final_branch, commit_message)

        # Create PR
        pr_title = f"Northstar Experiment: {instruction}"
        pr_body = format_pr_body(instruction, target_file, diff)
        pr_url = open_pr(target_repo, final_branch, base_branch, pr_title, pr_body)

        # Success
        result = {
            "status": "success",
            "pr_url": pr_url,
            "branch": final_branch,
            "files_modified": [target_file],
            "diff_summary": f"{len(diff.splitlines())} lines changed"
        }

        import json
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]

    except Exception as e:
        return [TextContent(
            type="text",
            text=f"Error executing code change: {str(e)}"
        )]

    finally:
        # Cleanup
        if repo_path:
            cleanup_repo(repo_path)


async def main():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
