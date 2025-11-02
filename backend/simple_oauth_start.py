"""Simple OAuth starter using Metorial SDK."""

import asyncio
import os
from dotenv import load_dotenv
from metorial import Metorial

load_dotenv()

METORIAL_API_KEY = os.getenv("METORIAL_API_KEY")
SLACK_DEPLOYMENT_ID = os.getenv("SLACK_DEPLOYMENT_ID")

async def start_oauth():
    metorial = Metorial(api_key=METORIAL_API_KEY)

    print("=" * 60)
    print("Starting Slack OAuth Flow")
    print("=" * 60)
    print(f"Slack Deployment ID: {SLACK_DEPLOYMENT_ID}\n")

    try:
        # Start OAuth using Metorial SDK
        oauth_session = metorial.oauth.sessions.create(
            server_deployment_id=SLACK_DEPLOYMENT_ID
        )

        auth_url = oauth_session.url
        session_id = oauth_session.id

        print("✓ OAuth flow started successfully!\n")
        print(f"Session ID: {session_id}\n")
        print("=" * 60)
        print("PLEASE OPEN THIS URL TO AUTHORIZE:")
        print("=" * 60)
        print(f"\n{auth_url}\n")
        print("=" * 60)
        print("\nAfter completing authorization in your browser:")
        print(f"1. Copy this session ID: {session_id}")
        print("2. Update your .env file:")
        print(f"   SLACK_OAUTH_SESSION_ID={session_id}")
        print("3. Run test_list_channels.py to verify")
        print("=" * 60)

    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(start_oauth())
