"""Northstar FastAPI Orchestrator - AI-powered experimentation platform."""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from metorial import Metorial
from openai import AsyncOpenAI
import os
import tempfile
import shutil
from pathlib import Path
from dotenv import load_dotenv
from captain_client import CaptainClient
from repo_indexer import (
    clone_repository,
    get_indexable_files,
    read_key_files,
    analyze_repository_structure,
    prepare_file_for_captain
)

load_dotenv()

app = FastAPI(
    title="Northstar API",
    description="Autonomous AI agent for product experimentation",
    version="0.1.0"
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Metorial, OpenAI, and Captain
metorial = Metorial(api_key=os.getenv("METORIAL_API_KEY"))
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
slack_deployment_id = os.getenv("SLACK_DEPLOYMENT_ID")
github_deployment_id = os.getenv("GITHUB_DEPLOYMENT_ID", "srv_0mg8iy70b29Y2sPqULfav8")
northstar_mcp_deployment_id = os.getenv("NORTHSTAR_MCP_DEPLOYMENT_ID")  # Will set after deploying

# Initialize Captain client (optional - will be None if not configured)
try:
    captain = CaptainClient()
except ValueError:
    captain = None
    print("Warning: Captain not configured - knowledge base features disabled")


# Request/Response Models
class OAuthCompleteRequest(BaseModel):
    session_id: str


class ProposeExperimentRequest(BaseModel):
    oauth_session_id: str


class ExecuteExperimentRequest(BaseModel):
    proposal_id: str
    instruction: str
    update_block: str
    oauth_session_id: str
    rollout_pct: int = 20


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Northstar API",
        "version": "0.1.0"
    }


@app.get("/oauth/start")
async def start_oauth():
    """
    Step 1: Create OAuth session for Slack.
    Frontend should redirect user to auth_url.
    """
    oauth_session = metorial.oauth.sessions.create(
        server_deployment_id=slack_deployment_id
    )
    return {
        "session_id": oauth_session.id,
        "auth_url": oauth_session.url
    }


@app.get("/oauth/complete")
async def complete_oauth(session_id: str):
    """
    Step 2: Wait for OAuth completion after user authorizes.
    """
    session = metorial.oauth.sessions.get(session_id)
    await metorial.oauth.wait_for_completion(session)
    return {
        "status": "success",
        "message": "OAuth complete",
        "session_id": session_id
    }


@app.post("/northstar/propose")
async def propose_experiment(req: ProposeExperimentRequest):
    """
    Generate an experiment proposal using Metorial + Northstar MCP.

    This uses the AI to:
    1. Call the propose_experiment MCP tool
    2. Return a structured proposal
    """
    try:
        # Determine which deployments to use
        deployments = [{
            "serverDeploymentId": slack_deployment_id,
            "oauthSessionId": req.oauth_session_id
        }]

        # Add Northstar MCP if deployed
        if northstar_mcp_deployment_id:
            deployments.append({
                "serverDeploymentId": northstar_mcp_deployment_id
            })

        result = await metorial.run(
            client=openai_client,
            message="""
            Use the propose_experiment tool to generate an experiment proposal.
            Return the proposal as JSON.
            """,
            model="gpt-4o",
            server_deployments=deployments,
            max_steps=5
        )

        return {
            "status": "success",
            "proposal": result.text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/northstar/execute")
async def execute_experiment(req: ExecuteExperimentRequest):
    """
    Execute an approved experiment using Metorial orchestration.

    This uses Metorial to:
    1. Call execute_code_change MCP tool (Morph + GitHub)
    2. Post result to Slack
    3. Return PR URL
    """
    try:
        # Determine which deployments to use
        deployments = [
            {
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": req.oauth_session_id
            },
            {
                "serverDeploymentId": github_deployment_id
            }
        ]

        # Add Northstar MCP if deployed
        if northstar_mcp_deployment_id:
            deployments.append({
                "serverDeploymentId": northstar_mcp_deployment_id
            })

        # Let Metorial orchestrate the entire flow
        result = await metorial.run(
            client=openai_client,
            message=f"""
            Execute this experiment:

            Experiment ID: {req.proposal_id}
            Instruction: {req.instruction}
            Rollout: {req.rollout_pct}%

            Steps:
            1. Use the execute_code_change tool with this update:
               {req.update_block}

            2. Once the PR is created, post a message to Slack announcing:
               "Experiment {req.proposal_id} deployed to {req.rollout_pct}% of users. PR: [url]"

            3. Return the PR URL in your response.
            """,
            model="gpt-4o",
            server_deployments=deployments,
            max_steps=10
        )

        return {
            "status": "success",
            "result": result.text,
            "proposal_id": req.proposal_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SlackMessageRequest(BaseModel):
    message: str
    oauth_session_id: str


class InitializeRepoRequest(BaseModel):
    repo: str  # Format: "owner/repo"
    oauth_session_id: str  # For Slack notifications


class QueryKnowledgeRequest(BaseModel):
    repo: str  # Format: "owner/repo"
    query: str


@app.post("/slack/message")
async def send_slack_message(req: SlackMessageRequest):
    """
    Send a message to Slack via Metorial.
    Used for notifications and updates.
    """
    try:
        result = await metorial.run(
            client=openai_client,
            message=f"""Post this message to Slack: "{req.message}"

Use the available Slack tools to post to any public channel.""",
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": req.oauth_session_id
            }],
            max_steps=10
        )

        return {
            "status": "success",
            "result": result.text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/northstar/initialize-repo")
async def initialize_repo(req: InitializeRepoRequest, background_tasks: BackgroundTasks):
    """
    Initialize a repository in the knowledge base.

    This endpoint:
    1. Clones the repository locally
    2. Reads and analyzes actual files
    3. Creates a Captain database
    4. Indexes files into Captain
    5. Posts detailed analysis to Slack
    """
    if not captain:
        raise HTTPException(
            status_code=503,
            detail="Captain not configured - set CAPTAIN_API_KEY and CAPTAIN_ORGANIZATION_ID"
        )

    database_name = req.repo.replace("/", "_").replace("-", "_")
    repo_path = None

    try:
        # 1. Clone the repository
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            repo_url = f"https://{github_token}@github.com/{req.repo}.git"
        else:
            repo_url = f"https://github.com/{req.repo}.git"

        temp_dir = Path(tempfile.mkdtemp())
        repo_path = temp_dir / "repo"

        clone_repository(repo_url, repo_path)

        # 2. Read key files for analysis
        key_files_content = read_key_files(repo_path)

        # 3. Analyze repository structure
        repo_structure = analyze_repository_structure(repo_path)

        # 4. Get indexable files
        indexable_files = get_indexable_files(repo_path)

        # 5. Read ALL indexable files for comprehensive analysis
        all_file_contents = {}

        # Start with key files
        all_file_contents.update(key_files_content)

        # Read all source code and other indexable files
        for file_path in indexable_files:
            try:
                relative_path = str(file_path.relative_to(repo_path))
                # Skip if already read as a key file
                if relative_path not in all_file_contents:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    # Limit individual file size to avoid overwhelming the context
                    all_file_contents[relative_path] = content[:10000]  # First 10k chars per file
            except Exception as e:
                print(f"Failed to read {file_path}: {e}")
                continue

        # 6. Build comprehensive context for AI analysis
        context = f"""
Repository: {req.repo}

=== REPOSITORY STRUCTURE ===
Total Files: {repo_structure['total_files']}
Languages Detected: {', '.join(repo_structure['languages_detected'])}
Directories: {len(repo_structure['directories'])}

File Types:
{chr(10).join(f"  {ext}: {count}" for ext, count in sorted(repo_structure['file_counts_by_type'].items(), key=lambda x: -x[1])[:10])}

=== ALL FILE CONTENTS ({len(all_file_contents)} files) ===
"""

        # Add ALL file contents to context
        for filename, content in sorted(all_file_contents.items()):
            context += f"\n{'='*60}\n"
            context += f"FILE: {filename} ({len(content)} chars)\n"
            context += f"{'='*60}\n"
            context += content
            if len(content) >= 10000:
                context += "\n\n... (truncated at 10,000 characters)"
            context += "\n"

        # 7. Have AI analyze ALL file contents
        result = await metorial.run(
            client=openai_client,
            message=f"""
Analyze this repository thoroughly based on ACTUAL file contents from ALL files:

{context}

You have access to the complete contents of ALL {len(all_file_contents)} files in this repository.

Provide a comprehensive analysis:
1. Product Overview: What does this product actually do? (based on README and actual code)
2. Architecture: What architectural patterns are used? (based on actual file structure, imports, and code organization)
3. Tech Stack: What frameworks, libraries, and tools are used? (based on actual dependencies and code)
4. Code Structure: Describe the actual functions, classes, and modules you see
5. Key Features: What specific features are implemented? (reference actual code)
6. Development Setup: How would a developer get started?

Then post this analysis to Slack in a well-formatted message starting with:
"📚 Knowledge Base Initialized: {req.repo}"

IMPORTANT:
- You have READ ALL {len(all_file_contents)} files - reference specific code, functions, and implementations
- Be specific and factual - cite actual file names, function names, and code snippets
- DO NOT use phrases like "likely includes" or "probably uses"
- Only state facts from the actual files you've read
            """,
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": req.oauth_session_id
            }],
            max_steps=10
        )

        # 8. Create Captain database
        try:
            captain.create_database(database_name)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise

        # 9. Index files into Captain in background
        async def index_files_background():
            try:
                for file_path in indexable_files[:100]:  # Limit to 100 files for MVP
                    try:
                        file_content = file_path.read_bytes()
                        file_info = prepare_file_for_captain(file_path, repo_path)

                        captain.upload_file(
                            database_name=database_name,
                            file_path=file_info['path'],
                            file_content=file_content,
                            metadata=file_info
                        )
                    except Exception as e:
                        print(f"Failed to index {file_path}: {e}")
                        continue
            finally:
                # Cleanup temp directory
                if repo_path and repo_path.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)

        background_tasks.add_task(index_files_background)

        return {
            "status": "success",
            "database_name": database_name,
            "analysis": result.text,
            "stats": {
                "total_files": repo_structure['total_files'],
                "files_read_and_analyzed": len(all_file_contents),
                "indexable_files": len(indexable_files),
                "languages": repo_structure['languages_detected'],
                "files_analyzed": list(all_file_contents.keys())
            },
            "message": f"Repository analyzed - read {len(all_file_contents)} files, indexing {len(indexable_files)} files in background"
        }

    except Exception as e:
        # Cleanup on error
        if repo_path and repo_path.exists():
            shutil.rmtree(repo_path.parent, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/northstar/query-knowledge")
async def query_knowledge(req: QueryKnowledgeRequest):
    """
    Query the knowledge base for a specific repository.

    Returns context-aware answers about the codebase, architecture, and product.
    """
    if not captain:
        raise HTTPException(
            status_code=503,
            detail="Captain not configured"
        )

    try:
        database_name = req.repo.replace("/", "_").replace("-", "_")

        # Query Captain database
        result = captain.query(
            database_name=database_name,
            query=req.query,
            include_files=True
        )

        return {
            "status": "success",
            "answer": result.get("response"),
            "relevant_files": result.get("relevant_files", []),
            "database_name": database_name
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/northstar/knowledge-status")
async def knowledge_status(repo: str):
    """
    Check if a repository has been initialized in the knowledge base.
    """
    if not captain:
        raise HTTPException(
            status_code=503,
            detail="Captain not configured"
        )

    try:
        databases = captain.list_databases()
        database_name = repo.replace("/", "_").replace("-", "_")

        repo_db = next(
            (db for db in databases if db["database_name"] == database_name),
            None
        )

        if not repo_db:
            return {
                "initialized": False,
                "database_name": database_name
            }

        # Get file count
        files = captain.list_files(database_name, limit=1)

        return {
            "initialized": True,
            "database_name": database_name,
            "database_info": repo_db,
            "has_files": len(files) > 0
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
