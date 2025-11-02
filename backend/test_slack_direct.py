"""Direct test of Slack integration via Metorial SDK."""

import asyncio
import os
from dotenv import load_dotenv
from metorial import Metorial
from openai import AsyncOpenAI

load_dotenv()

METORIAL_API_KEY = os.getenv("METORIAL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_DEPLOYMENT_ID = os.getenv("SLACK_DEPLOYMENT_ID")
SLACK_OAUTH_SESSION_ID = os.getenv("SLACK_OAUTH_SESSION_ID")

async def test_slack():
    print("=" * 60)
    print("Direct Slack Integration Test")
    print("=" * 60)
    print(f"Deployment: {SLACK_DEPLOYMENT_ID}")
    print(f"Session: {SLACK_OAUTH_SESSION_ID}")
    print()

    metorial = Metorial(api_key=METORIAL_API_KEY)
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    # Test 1: List channels
    print("Test 1: Listing Slack channels...")
    print("-" * 60)
    try:
        result = await metorial.run(
            client=openai_client,
            message="Use the Slack tools to list all public channels in the workspace. Show me the channel names.",
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": SLACK_DEPLOYMENT_ID,
                "oauthSessionId": SLACK_OAUTH_SESSION_ID
            }],
            max_steps=5
        )
        print(f"✓ Result: {result.text}")
        print()
    except Exception as e:
        print(f"✗ Error: {e}")
        print()

    # Test 2: Send a message
    print("Test 2: Sending a test message to Slack...")
    print("-" * 60)
    try:
        result = await metorial.run(
            client=openai_client,
            message="Post a message to the #general channel saying: '🎉 Northstar Slack integration test successful!'",
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": SLACK_DEPLOYMENT_ID,
                "oauthSessionId": SLACK_OAUTH_SESSION_ID
            }],
            max_steps=5
        )
        print(f"✓ Result: {result.text}")
        print()
    except Exception as e:
        print(f"✗ Error: {e}")
        print()

    # Test 3: Check available tools
    print("Test 3: Checking available Slack tools...")
    print("-" * 60)
    try:
        result = await metorial.run(
            client=openai_client,
            message="What Slack tools do you have access to? List all available Slack-related tools and their capabilities.",
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": SLACK_DEPLOYMENT_ID,
                "oauthSessionId": SLACK_OAUTH_SESSION_ID
            }],
            max_steps=3
        )
        print(f"✓ Result: {result.text}")
        print()
    except Exception as e:
        print(f"✗ Error: {e}")
        print()

    print("=" * 60)
    print("Test completed")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_slack())
