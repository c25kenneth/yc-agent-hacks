import asyncio
import os
from dotenv import load_dotenv
import google.generativeai as genai
from metorial import Metorial
from openai import AsyncOpenAI

load_dotenv()

async def main():
    # --- Setup clients ---
    metorial = Metorial(api_key=os.getenv("METORIAL_API_KEY"))

    openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


    slack_deployment_id = os.getenv("SLACK_DEPLOYMENT_ID")

    # --- Step 1: Create OAuth session for Slack ---
    print("🔗 Creating OAuth session...")
    oauth_session = metorial.oauth.sessions.create(
        server_deployment_id= slack_deployment_id
    )

    print("OAuth URLs for user authentication:") 
    print(f" Slack: {oauth_session.url}") 
    print("\n⏳ Waiting for OAuth completion...") 
    await metorial.oauth.wait_for_completion([oauth_session])

    # --- Step 2: Send a message using Gemini as the reasoning model ---
    prompt = "Send a Slack message to a channel saying 'Hello from Gemini + Metorial! 🎉'"

    result = await metorial.run(
        message=prompt,
        client=openai,
        model="gpt-4o",
        server_deployments=[
            {
                "serverDeploymentId": slack_deployment_id,
                "oauthSessionId": oauth_session.id
            }
        ],
        max_steps=10,

    )

    print("\n✅ Result from Metorial:")
    print(result.text)

if __name__ == "__main__":
    asyncio.run(main())
