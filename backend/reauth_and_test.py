"""
Re-authenticate with Slack OAuth and test channel listing.

This script:
1. Starts a new OAuth flow
2. Waits for you to complete authorization
3. Tests channel listing with the new session
"""

import asyncio
import os
import requests
from dotenv import load_dotenv
from metorial import Metorial
from openai import AsyncOpenAI

load_dotenv()

METORIAL_API_KEY = os.getenv("METORIAL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_DEPLOYMENT_ID = os.getenv("SLACK_DEPLOYMENT_ID")

print("=" * 60)
print("Slack OAuth Re-authentication and Channel Test")
print("=" * 60)

# Step 1: Start OAuth flow
print("\nStep 1: Starting OAuth flow...")
print(f"Slack Deployment ID: {SLACK_DEPLOYMENT_ID}")

try:
    response = requests.post(
        "https://api.metorial.com/v1/oauth/start",
        headers={
            "Authorization": f"Bearer {METORIAL_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "serverDeploymentId": SLACK_DEPLOYMENT_ID
        }
    )
    response.raise_for_status()
    oauth_data = response.json()

    auth_url = oauth_data.get("authorizationUrl")
    session_id = oauth_data.get("sessionId")

    print(f"\n✓ OAuth flow started successfully")
    print(f"Session ID: {session_id}")
    print("\n" + "=" * 60)
    print("AUTHORIZATION REQUIRED")
    print("=" * 60)
    print(f"\nPlease open this URL in your browser to authorize:")
    print(f"\n{auth_url}\n")
    print("After authorizing, press ENTER to continue...")
    print("=" * 60)

    input()

    # Step 2: Wait for OAuth completion
    print("\nStep 2: Checking OAuth completion...")

    metorial = Metorial(api_key=METORIAL_API_KEY)

    try:
        # Wait for completion (this will block until user authorizes)
        asyncio.run(metorial.oauth.wait_for_completion(session_id, timeout=300))
        print("✓ OAuth authorization completed successfully!")

        oauth_session_id = session_id  # The session_id IS the oauth_session_id

    except Exception as e:
        print(f"✗ OAuth completion error: {str(e)}")
        print("\nThis might mean:")
        print("1. You haven't authorized yet - please complete authorization in browser")
        print("2. The authorization timed out - try again")
        print("3. There was an error with the Slack app configuration")
        exit(1)

    # Step 3: Update .env file
    print("\nStep 3: Updating .env file with new OAuth session...")

    # Read current .env
    env_path = "/Users/tylerbordeaux/Documents/GitHub/yc-agent-hacks/backend/.env"
    with open(env_path, 'r') as f:
        lines = f.readlines()

    # Update SLACK_OAUTH_SESSION_ID
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('SLACK_OAUTH_SESSION_ID='):
            lines[i] = f'SLACK_OAUTH_SESSION_ID={oauth_session_id}\n'
            updated = True
            break

    if not updated:
        lines.append(f'SLACK_OAUTH_SESSION_ID={oauth_session_id}\n')

    # Write back
    with open(env_path, 'w') as f:
        f.writelines(lines)

    print(f"✓ Updated .env with new session ID: {oauth_session_id}")

    # Step 4: Test channel listing
    print("\nStep 4: Testing channel listing with new OAuth session...")

    async def test_channels():
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        result = await metorial.run(
            client=openai_client,
            message="""List ALL Slack channels that you can access.

For EACH channel, provide:
1. Channel name (with # prefix)
2. Channel ID
3. Whether it's public or private

Format as a clear list.""",
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": SLACK_DEPLOYMENT_ID,
                "oauthSessionId": oauth_session_id
            }],
            max_steps=10
        )

        return result.text

    result_text = asyncio.run(test_channels())

    print("\n" + "=" * 60)
    print("CHANNEL LISTING RESULT")
    print("=" * 60)
    print(result_text)
    print("=" * 60)

    # Check result
    result_lower = result_text.lower()
    if "error" in result_lower or "unable" in result_lower or "cannot" in result_lower:
        print("\n⚠️  WARNING: Still seeing permission issues!")
        print("\nThis suggests the Slack app needs additional OAuth scopes.")
        print("Please check the Metorial dashboard and ensure these scopes are added:")
        print("  - channels:read")
        print("  - chat:write")
        print("  - chat:write.public")
        print("  - channels:history")
    else:
        print("\n✓ SUCCESS! Channel listing appears to be working!")
        print(f"\nNew OAuth session ID saved to .env: {oauth_session_id}")
        print("\nYou can now use this session for Slack integration.")

except requests.exceptions.RequestException as e:
    print(f"\n✗ Error starting OAuth flow: {str(e)}")
    if hasattr(e.response, 'text'):
        print(f"Response: {e.response.text}")
except Exception as e:
    print(f"\n✗ Unexpected error: {str(e)}")
    import traceback
    traceback.print_exc()
