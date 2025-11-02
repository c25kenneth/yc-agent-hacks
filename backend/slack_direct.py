"""Direct Slack API integration (bypass Metorial MCP)."""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

def get_slack_token():
    """
    Get Slack OAuth token from Metorial session.
    Note: This requires extracting the token from the Metorial OAuth session.
    For now, you'll need to manually get a Slack token from api.slack.com
    """
    # TODO: Extract from Metorial session or use direct Slack OAuth
    return os.getenv("SLACK_BOT_TOKEN")  # Add this to .env


def send_slack_message(channel: str, text: str):
    """Send a message to Slack using the Web API."""
    token = get_slack_token()
    if not token:
        print("No Slack token available")
        return False

    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "channel": channel,
        "text": text
    }

    response = requests.post(url, headers=headers, json=data)
    result = response.json()

    if result.get("ok"):
        print(f"✓ Message sent to {channel}")
        return True
    else:
        print(f"✗ Error: {result.get('error')}")
        return False


if __name__ == "__main__":
    # Test
    send_slack_message("#general", "🎉 Test from Northstar!")
