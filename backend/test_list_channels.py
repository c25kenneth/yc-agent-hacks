"""Quick test to list accessible Slack channels."""

import asyncio
import os
from dotenv import load_dotenv
from metorial import Metorial
from openai import AsyncOpenAI

load_dotenv()

async def list_channels():
    """List all Slack channels accessible to the current OAuth session."""

    METORIAL_API_KEY = os.getenv("METORIAL_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    SLACK_DEPLOYMENT_ID = os.getenv("SLACK_DEPLOYMENT_ID")
    SLACK_OAUTH_SESSION_ID = os.getenv("SLACK_OAUTH_SESSION_ID")

    print("=" * 60)
    print("Slack Channel Access Test")
    print("=" * 60)
    print(f"\nUsing OAuth Session: {SLACK_OAUTH_SESSION_ID}")
    print(f"Slack Deployment: {SLACK_DEPLOYMENT_ID}\n")

    metorial = Metorial(api_key=METORIAL_API_KEY)
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    try:
        print("Requesting list of accessible Slack channels...\n")

        result = await metorial.run(
            client=openai_client,
            message="""List ALL Slack channels that you can access with detailed information.

For EACH channel, provide:
1. Channel name (with # prefix)
2. Channel ID
3. Whether it's public or private
4. Member count if available

Format the output as a clear, readable list.""",
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": SLACK_DEPLOYMENT_ID,
                "oauthSessionId": SLACK_OAUTH_SESSION_ID
            }],
            max_steps=10
        )

        print("=" * 60)
        print("RESULT:")
        print("=" * 60)
        print(result.text)
        print("=" * 60)

        # Check for errors
        result_lower = result.text.lower()
        if "error" in result_lower or "permission" in result_lower or "unable" in result_lower:
            print("\n⚠️  WARNING: Response may indicate permission issues")
            print("This suggests the OAuth session lacks 'channels:read' scope")
        else:
            print("\n✓ Successfully retrieved channel information")

    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(list_channels())
