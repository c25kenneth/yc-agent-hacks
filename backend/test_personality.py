"""Test script to send demo messages showcasing the new personality."""

import asyncio
import os
from dotenv import load_dotenv
from metorial import Metorial
from openai import AsyncOpenAI

load_dotenv()

async def send_demo_messages():
    """Send demo messages with the new personality."""

    metorial = Metorial(api_key=os.getenv("METORIAL_API_KEY"))
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    slack_deployment_id = os.getenv("SLACK_DEPLOYMENT_ID")
    slack_oauth_session_id = os.getenv("SLACK_OAUTH_SESSION_ID")

    # Test channel
    channel = "C09QL9V1J1F"

    print("📤 Sending personality demo messages to Slack...")

    # Demo 1: CODE_CHANGE with new personality
    print("\n1️⃣ Sending CODE_CHANGE with personality...")
    code_change_message = """On it.

*Code change executed*

*PR:* https://github.com/tylerbordeaux/northstar-demo/pull/456
*Files changed:* 2 file(s)
*Changes:* Added skeleton loaders to dashboard components

This should make the dashboard feel faster. Perceived performance improved without touching backend."""

    await metorial.run(
        message=f"Post this exact message to Slack channel {channel}:\n\n{code_change_message}",
        server_deployments=[
            {
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": slack_oauth_session_id
            }
        ],
        client=openai_client,
        model="gpt-4o",
        max_steps=3
    )
    print("✅ Code change sent")

    await asyncio.sleep(2)

    # Demo 2: EXPERIMENT_PROPOSAL with personality
    print("\n2️⃣ Sending EXPERIMENT_PROPOSAL with personality...")
    experiment_message = """*New experiment proposed:*
Add animated progress indicators during data sync

*Category:* UX Enhancement
*Confidence:* 78%
*Expected impact:* +15% user_retention
*PR Ready:* True

*Rationale:*
Users abandon the app during sync operations. No feedback creates uncertainty. Adding progress indicators should reduce abandonment during these critical moments.

*Technical Plan:*
• src/sync/SyncManager.ts: Add progress tracking hooks
• src/components/ProgressBar.jsx: Implement animated progress component
• src/utils/syncEvents.ts: Emit progress events during sync

Looks promising. This addresses a key friction point."""

    await metorial.run(
        message=f"Post this exact message to Slack channel {channel}:\n\n{experiment_message}",
        server_deployments=[
            {
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": slack_oauth_session_id
            }
        ],
        client=openai_client,
        model="gpt-4o",
        max_steps=3
    )
    print("✅ Experiment proposal sent")

    await asyncio.sleep(2)

    # Demo 3: ANALYTICS with personality
    print("\n3️⃣ Sending ANALYTICS with personality...")
    analytics_message = """*Analytics Report*

*Metric:* Daily Active Users (DAU)
*Current:* 3,124 users
*Trend:* Up 22% from last week

*Key insights:*
• Growth driven by mobile improvements. Desktop stayed flat.
• New user retention hit 65%. Best we've seen this quarter.
• Peak hours shifted to 2-4pm. International adoption is growing.

Looks good. Mobile changes are paying off."""

    await metorial.run(
        message=f"Post this exact message to Slack channel {channel}:\n\n{analytics_message}",
        server_deployments=[
            {
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": slack_oauth_session_id
            }
        ],
        client=openai_client,
        model="gpt-4o",
        max_steps=3
    )
    print("✅ Analytics report sent")

    print("\n✨ All personality demo messages sent successfully!")


if __name__ == "__main__":
    asyncio.run(send_demo_messages())
