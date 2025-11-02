"""Northstar FastAPI Orchestrator - AI-powered experimentation platform."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from metorial import Metorial
import os
from dotenv import load_dotenv

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

# Initialize Metorial
metorial = Metorial(api_key=os.getenv("METORIAL_API_KEY"))
slack_deployment_id = os.getenv("SLACK_DEPLOYMENT_ID")
github_deployment_id = os.getenv("GITHUB_DEPLOYMENT_ID", "srv_0mg8iy70b29Y2sPqULfav8")
northstar_mcp_deployment_id = os.getenv("NORTHSTAR_MCP_DEPLOYMENT_ID")  # Will set after deploying


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
    await metorial.oauth.wait_for_completion_by_id(session_id)
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


@app.post("/slack/message")
async def send_slack_message(message: str, oauth_session_id: str):
    """
    Send a message to Slack via Metorial.
    Used for notifications and updates.
    """
    try:
        result = await metorial.run(
            message=f"Send a Slack message: {message}",
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": oauth_session_id
            }],
            max_steps=3
        )

        return {
            "status": "success",
            "result": result.text
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
