"""Test PostHog integration with the autonomous agent."""

import asyncio
import os
from dotenv import load_dotenv
from metorial import Metorial
from openai import AsyncOpenAI

load_dotenv()


async def test_posthog():
    """Test that PostHog MCP integration works."""

    print("🧪 Testing PostHog Integration\n")

    # Load environment variables
    metorial_api_key = os.getenv("METORIAL_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    posthog_deployment_id = os.getenv("POSTHOG_DEPLOYMENT_ID")
    slack_deployment_id = os.getenv("SLACK_DEPLOYMENT_ID")
    slack_oauth_session_id = os.getenv("SLACK_OAUTH_SESSION_ID")

    # Verify all required environment variables are set
    if not all([metorial_api_key, openai_api_key, posthog_deployment_id, slack_deployment_id, slack_oauth_session_id]):
        print("❌ Missing required environment variables:")
        if not metorial_api_key:
            print("  - METORIAL_API_KEY")
        if not openai_api_key:
            print("  - OPENAI_API_KEY")
        if not posthog_deployment_id:
            print("  - POSTHOG_DEPLOYMENT_ID")
        if not slack_deployment_id:
            print("  - SLACK_DEPLOYMENT_ID")
        if not slack_oauth_session_id:
            print("  - SLACK_OAUTH_SESSION_ID")
        return False

    print("✅ All environment variables loaded\n")
    print(f"PostHog Deployment ID: {posthog_deployment_id}")
    print(f"Slack Deployment ID: {slack_deployment_id}\n")

    # Initialize clients
    metorial = Metorial(api_key=metorial_api_key)
    openai_client = AsyncOpenAI(api_key=openai_api_key)

    # Test 1: PostHog MCP can be accessed
    print("📊 Test 1: Testing PostHog MCP availability...")
    try:
        result = await metorial.run(
            client=openai_client,
            message="List the available PostHog tools and what they can do. Just describe them briefly.",
            model="gpt-4o",
            server_deployments=[
                {"serverDeploymentId": posthog_deployment_id}
            ],
            max_steps=5
        )
        print(f"✅ PostHog MCP is accessible")
        print(f"Response: {result.text[:200]}...\n")
    except Exception as e:
        print(f"❌ Failed to access PostHog MCP: {e}\n")
        return False

    # Test 2: Query PostHog for project info
    print("📊 Test 2: Querying PostHog for project information...")
    try:
        result = await metorial.run(
            client=openai_client,
            message="Tell me about the PostHog project. What metrics or data are available?",
            model="gpt-4o",
            server_deployments=[
                {"serverDeploymentId": posthog_deployment_id}
            ],
            max_steps=10
        )
        print(f"✅ Successfully queried PostHog")
        print(f"Response: {result.text}\n")
    except Exception as e:
        print(f"❌ Failed to query PostHog: {e}\n")
        return False

    print("✅ All PostHog integration tests passed!")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_posthog())
    exit(0 if success else 1)
