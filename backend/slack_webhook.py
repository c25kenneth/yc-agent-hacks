"""
Slack Webhook Handler for Northstar conversational bot.

Receives Slack events when messages mention "northstar" and responds autonomously.
"""

from fastapi import Request, HTTPException
from pydantic import BaseModel
from metorial import Metorial
from openai import AsyncOpenAI
import os
import json
import logging

logger = logging.getLogger(__name__)

# Initialize clients
metorial = Metorial(api_key=os.getenv("METORIAL_API_KEY"))
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
slack_deployment_id = os.getenv("SLACK_DEPLOYMENT_ID")

class SlackEvent(BaseModel):
    """Slack event structure."""
    type: str
    text: str = None
    user: str = None
    channel: str = None
    ts: str = None

class SlackWebhookPayload(BaseModel):
    """Slack webhook payload."""
    token: str = None
    team_id: str = None
    event: SlackEvent = None
    type: str = None
    challenge: str = None  # For URL verification

async def handle_slack_event(request: Request):
    """
    Handle incoming Slack events.

    This endpoint:
    1. Verifies Slack challenges (URL verification)
    2. Listens for messages mentioning "northstar"
    3. Responds conversationally using GPT-4o
    """
    try:
        body = await request.json()

        # Handle URL verification challenge
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge")}

        # Handle app_mention or message events
        event = body.get("event", {})
        event_type = event.get("type")

        # Ignore bot messages to prevent loops
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return {"ok": True}

        # Check if message mentions "northstar" (case-insensitive)
        text = event.get("text", "").lower()
        if "northstar" not in text:
            return {"ok": True}

        # Extract channel and original message
        channel = event.get("channel")
        user_message = event.get("text", "")
        user_id = event.get("user")

        logger.info(f"Northstar mentioned by user {user_id} in channel {channel}: {user_message}")

        # Respond conversationally using GPT-4o via Metorial
        await respond_to_slack_message(channel, user_message, user_id)

        return {"ok": True}

    except Exception as e:
        logger.error(f"Error handling Slack event: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def respond_to_slack_message(channel: str, message: str, user_id: str):
    """
    Respond to a Slack message mentioning Northstar.

    Uses GPT-4o to generate a conversational response that mirrors
    the user's tone and responds personably.
    """
    try:
        # Get OAuth session from environment (should be stored per workspace)
        oauth_session_id = os.getenv("SLACK_OAUTH_SESSION_ID")

        if not slack_deployment_id or not oauth_session_id:
            logger.warning("Slack not configured - skipping response")
            return

        # Use Metorial to autonomously respond
        result = await metorial.run(
            client=openai_client,
            message=f"""
            You are Northstar, an AI experimentation assistant for a YC-backed startup.

            User message: "{message}"

            Craft a response with a clean, minimal tone:
            - NO emojis ever
            - NO exclamation marks
            - Keep it concise (1-2 sentences max)
            - Be direct and professional
            - Mirror their level of formality
            - If they're casual ("hey", "what's up"), be casual back
            - If asking about work, be helpful and specific

            Examples of good responses:
            - "Hey, what's up?"
            - "All good. Need help with anything?"
            - "I can help you propose an experiment if you'd like"

            Bad responses (don't do this):
            - "Hey there! :blush: Just let me know how I can assist you today!"
            - "All systems are up and running smoothly on my end!"

            IMPORTANT: Post ONLY ONE message to Slack channel {channel}. Do not post multiple messages or revisions.
            """,
            model="gpt-4o",
            server_deployments=[
                {
                    "serverDeploymentId": slack_deployment_id,
                    "oauthSessionId": oauth_session_id
                }
            ],
            max_steps=1
        )

        logger.info(f"Responded to Northstar mention in channel {channel}")

    except Exception as e:
        logger.error(f"Error responding to Slack message: {str(e)}")

async def handle_slash_command(request: Request):
    """
    Handle Slack slash commands like /northstar.

    Example: /northstar propose an experiment
    """
    try:
        form_data = await request.form()

        command = form_data.get("command")
        text = form_data.get("text", "")
        user_id = form_data.get("user_id")
        channel_id = form_data.get("channel_id")

        logger.info(f"Slash command {command} from user {user_id}: {text}")

        # Respond immediately (Slack requires response within 3 seconds)
        response = {
            "response_type": "in_channel",
            "text": f"Processing your request: {text}"
        }

        # Process the command asynchronously
        # This would trigger the same conversational flow
        await respond_to_slack_message(channel_id, text, user_id)

        return response

    except Exception as e:
        logger.error(f"Error handling slash command: {str(e)}")
        return {
            "response_type": "ephemeral",
            "text": f"Error processing command: {str(e)}"
        }
