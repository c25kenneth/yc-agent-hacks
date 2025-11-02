#!/usr/bin/env python3
"""Test script to send a Slack message."""

import requests
import json
import sys
import time

BASE_URL = "http://localhost:8000"

def send_slack_message(message: str, oauth_session_id: str = None):
    """Send a Slack message using the API."""
    if not oauth_session_id:
        # Start OAuth flow
        print("Starting OAuth session...")
        response = requests.get(f"{BASE_URL}/oauth/start")
        response.raise_for_status()
        oauth_data = response.json()
        session_id = oauth_data["session_id"]
        auth_url = oauth_data["auth_url"]
        
        print(f"\nOAuth session created:")
        print(f"  Session ID: {session_id}")
        print(f"  Auth URL: {auth_url}")
        print(f"\n⚠️  You need to visit the Auth URL and authorize Slack access.")
        print(f"   After authorization, wait a few seconds, then run:")
        print(f"   python test_slack_message.py '{message}' {session_id}")
        return None
    else:
        # Try to complete OAuth if needed
        try:
            print(f"Checking OAuth session: {oauth_session_id}")
            response = requests.get(f"{BASE_URL}/oauth/complete?session_id={oauth_session_id}")
            if response.status_code == 200:
                print("OAuth session completed!")
        except Exception as e:
            print(f"Note: {e}")
        
        # Send message
        print(f"\nSending message: '{message}'")
        response = requests.post(
            f"{BASE_URL}/slack/message",
            json={
                "message": message,
                "oauth_session_id": oauth_session_id
            }
        )
        response.raise_for_status()
        result = response.json()
        
        print(f"\n✅ Status: {result.get('status')}")
        print(f"📨 Result: {result.get('result')}")
        return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_slack_message.py <message> [oauth_session_id]")
        print("\nExample:")
        print("  python test_slack_message.py 'hello'")
        print("  python test_slack_message.py 'hello' soas_xxxxx")
        sys.exit(1)
    
    message = sys.argv[1]
    oauth_session_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    send_slack_message(message, oauth_session_id)

