from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from metorial import Metorial
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# --- CORS setup ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

metorial = Metorial(api_key=os.getenv("METORIAL_API_KEY"))
slack_deployment_id = os.getenv("SLACK_DEPLOYMENT_ID")


class MessageRequest(BaseModel):
    prompt: str


@app.get("/oauth/start")
async def start_oauth():
    """Step 1: Frontend requests OAuth session URL."""
    oauth_session = metorial.oauth.sessions.create(
        server_deployment_id=slack_deployment_id
    )
    return {"session_id": oauth_session.id, "auth_url": oauth_session.url}


@app.get("/oauth/complete")
async def complete_oauth(session_id: str):
    """Step 2: Called by frontend after redirect back from Slack."""
    await metorial.oauth.wait_for_completion_by_id(session_id)
    return {"message": "OAuth complete", "session_id": session_id}


@app.post("/send_message")
async def send_message(req: MessageRequest):
    """Step 3: Now safely run task once OAuth is done."""
    try:
        result = await metorial.run(
            message=req.prompt,
            model="gpt-4o",
            client=None,  # or your reasoning client like AsyncOpenAI
            server_deployments=[{
                "serverDeploymentId": slack_deployment_id,
                # use the OAuth session your frontend tracked
                "oauthSessionId": req.oauth_session_id
            }],
            max_steps=10
        )
        return {"result": result.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




# import asyncio
# import os
# from dotenv import load_dotenv
# import google.generativeai as genai
# from metorial import Metorial
# from openai import AsyncOpenAI

# load_dotenv()

# async def main():
#     # --- Setup clients ---
#     metorial = Metorial(api_key=os.getenv("METORIAL_API_KEY"))

#     openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


#     slack_deployment_id = os.getenv("SLACK_DEPLOYMENT_ID")

#     # --- Step 1: Create OAuth session for Slack ---
#     print("🔗 Creating OAuth session...")
#     oauth_session = metorial.oauth.sessions.create(
#         server_deployment_id= slack_deployment_id
#     )

#     print("OAuth URLs for user authentication:") 
#     print(f" Slack: {oauth_session.url}") 
#     print("\n⏳ Waiting for OAuth completion...") 
#     await metorial.oauth.wait_for_completion([oauth_session])

#     # --- Step 2: Send a message using Gemini as the reasoning model ---
#     prompt = "Send a Slack message to a channel saying 'Hello from Gemini + Metorial! 🎉'"

#     result = await metorial.run(
#         message=prompt,
#         client=openai,
#         model="gpt-4o",
#         server_deployments=[
#             {
#                 "serverDeploymentId": slack_deployment_id,
#                 "oauthSessionId": oauth_session.id
#             }
#         ],
#         max_steps=10,

#     )

#     print("\n✅ Result from Metorial:")
#     print(result.text)

# if __name__ == "__main__":
#     asyncio.run(main())
