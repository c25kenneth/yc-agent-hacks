"""
Test script for Slack MCP integration via Metorial.

This script tests:
1. Basic Slack message sending
2. Channel listing capabilities
3. OAuth session validation
4. Permission diagnostics

Usage:
    python test_slack_mcp.py
"""

import asyncio
import os
from dotenv import load_dotenv
from metorial import Metorial
from openai import AsyncOpenAI

load_dotenv()

# Configuration
METORIAL_API_KEY = os.getenv("METORIAL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SLACK_DEPLOYMENT_ID = os.getenv("SLACK_DEPLOYMENT_ID")
SLACK_OAUTH_SESSION_ID = os.getenv("SLACK_OAUTH_SESSION_ID")

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_section(title):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(message):
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")

def print_error(message):
    """Print an error message."""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")

def print_warning(message):
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")

def print_info(message):
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")


async def test_configuration():
    """Test 1: Verify all required configuration is present."""
    print_section("Test 1: Configuration Check")

    all_ok = True

    if METORIAL_API_KEY:
        print_success(f"METORIAL_API_KEY: {METORIAL_API_KEY[:20]}...")
    else:
        print_error("METORIAL_API_KEY: NOT SET")
        all_ok = False

    if OPENAI_API_KEY:
        print_success(f"OPENAI_API_KEY: {OPENAI_API_KEY[:20]}...")
    else:
        print_error("OPENAI_API_KEY: NOT SET")
        all_ok = False

    if SLACK_DEPLOYMENT_ID:
        print_success(f"SLACK_DEPLOYMENT_ID: {SLACK_DEPLOYMENT_ID}")
    else:
        print_error("SLACK_DEPLOYMENT_ID: NOT SET")
        all_ok = False

    if SLACK_OAUTH_SESSION_ID:
        print_success(f"SLACK_OAUTH_SESSION_ID: {SLACK_OAUTH_SESSION_ID}")
    else:
        print_error("SLACK_OAUTH_SESSION_ID: NOT SET")
        all_ok = False

    return all_ok


async def test_list_channels():
    """Test 2: Try to list Slack channels (requires channels:read scope)."""
    print_section("Test 2: List Slack Channels")

    try:
        metorial = Metorial(api_key=METORIAL_API_KEY)
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        print_info("Attempting to list Slack channels...")
        print_info("This requires the 'channels:read' OAuth scope")

        result = await metorial.run(
            client=openai_client,
            message="List all public Slack channels. Return the channel names and IDs.",
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": SLACK_DEPLOYMENT_ID,
                "oauthSessionId": SLACK_OAUTH_SESSION_ID
            }],
            max_steps=5
        )

        print_success("Channel listing request completed")
        print_info(f"Result: {result.text[:500]}")

        # Check for permission errors
        result_lower = result.text.lower()
        if "permission" in result_lower or "not authorized" in result_lower or "missing" in result_lower:
            print_error("Permission issue detected in response")
            return False
        elif "error" in result_lower:
            print_warning("Error detected in response")
            return False
        else:
            print_success("No obvious errors detected")
            return True

    except Exception as e:
        print_error(f"Failed to list channels: {str(e)}")
        return False


async def test_send_message():
    """Test 3: Send a test message to Slack."""
    print_section("Test 3: Send Test Message")

    try:
        metorial = Metorial(api_key=METORIAL_API_KEY)
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        test_message = "🧪 Slack MCP Test: Integration test successful!"

        print_info(f"Sending message: '{test_message}'")
        print_info("This requires 'chat:write' OAuth scope")

        result = await metorial.run(
            client=openai_client,
            message=f"""Post this message to the #northstar Slack channel: "{test_message}"

Use the available Slack tools to post the message.""",
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": SLACK_DEPLOYMENT_ID,
                "oauthSessionId": SLACK_OAUTH_SESSION_ID
            }],
            max_steps=10
        )

        print_success("Message sending request completed")
        print_info(f"Result: {result.text[:500]}")

        # Check for success indicators
        result_lower = result.text.lower()
        if "posted" in result_lower or "sent" in result_lower or "success" in result_lower:
            print_success("Message appears to have been sent successfully")
            return True
        elif "permission" in result_lower or "not authorized" in result_lower:
            print_error("Permission issue detected")
            return False
        elif "error" in result_lower or "failed" in result_lower:
            print_error("Error detected in response")
            return False
        else:
            print_warning("Unclear if message was sent - check Slack manually")
            return None

    except Exception as e:
        print_error(f"Failed to send message: {str(e)}")
        return False


async def test_read_messages():
    """Test 4: Try to read messages from a channel (requires channels:history scope)."""
    print_section("Test 4: Read Channel Messages")

    try:
        metorial = Metorial(api_key=METORIAL_API_KEY)
        openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        print_info("Attempting to read recent messages from #northstar channel...")
        print_info("This requires 'channels:history' OAuth scope")

        result = await metorial.run(
            client=openai_client,
            message="Read the last 3 messages from the #northstar Slack channel and summarize them.",
            model="gpt-4o",
            server_deployments=[{
                "serverDeploymentId": SLACK_DEPLOYMENT_ID,
                "oauthSessionId": SLACK_OAUTH_SESSION_ID
            }],
            max_steps=5
        )

        print_success("Message reading request completed")
        print_info(f"Result: {result.text[:500]}")

        # Check for permission errors
        result_lower = result.text.lower()
        if "permission" in result_lower or "not authorized" in result_lower:
            print_error("Permission issue detected")
            return False
        elif "cannot" in result_lower or "unable" in result_lower:
            print_warning("May lack permissions to read messages")
            return False
        else:
            print_success("No obvious errors detected")
            return True

    except Exception as e:
        print_error(f"Failed to read messages: {str(e)}")
        return False


async def diagnose_permissions():
    """Test 5: Diagnose what permissions are available."""
    print_section("Test 5: Permission Diagnosis")

    print_info("Based on test results, diagnosing OAuth scope issues...")

    # Run all tests
    channels_ok = await test_list_channels()
    message_ok = await test_send_message()
    read_ok = await test_read_messages()

    print_section("Diagnosis Summary")

    print_info("Required OAuth Scopes for Full Functionality:")
    print("  • channels:read - List public channels")
    print("  • chat:write - Post messages")
    print("  • chat:write.public - Post to channels without joining")
    print("  • channels:history - Read channel messages")

    print("\nTest Results:")
    if channels_ok:
        print_success("channels:read - WORKING")
    else:
        print_error("channels:read - MISSING OR FAILING")

    if message_ok:
        print_success("chat:write - WORKING")
    elif message_ok is False:
        print_error("chat:write - MISSING OR FAILING")
    else:
        print_warning("chat:write - UNCLEAR (check Slack manually)")

    if read_ok:
        print_success("channels:history - WORKING")
    else:
        print_error("channels:history - MISSING OR FAILING")

    # Recommendations
    print_section("Recommendations")

    if not (channels_ok and message_ok and read_ok):
        print_warning("Some permissions appear to be missing or failing")
        print("\nTo fix this:")
        print("1. Go to Metorial dashboard")
        print(f"2. Navigate to Slack deployment: {SLACK_DEPLOYMENT_ID}")
        print("3. Add missing OAuth scopes:")
        print("   - channels:read")
        print("   - chat:write")
        print("   - chat:write.public")
        print("   - channels:history")
        print("4. Create a new OAuth session:")
        print("   curl -X POST https://api.metorial.com/v1/oauth/start \\")
        print(f"     -H 'Authorization: Bearer {METORIAL_API_KEY[:20]}...' \\")
        print("     -H 'Content-Type: application/json' \\")
        print(f"     -d '{{\"serverDeploymentId\": \"{SLACK_DEPLOYMENT_ID}\"}}'")
        print("5. Complete authorization in browser")
        print("6. Update SLACK_OAUTH_SESSION_ID in .env with new session ID")
    else:
        print_success("All permissions appear to be working correctly!")
        print_info("Your Slack integration is ready to use")


async def main():
    """Run all tests."""
    print(f"\n{Colors.BOLD}Slack MCP Integration Test Suite{Colors.RESET}")
    print(f"{Colors.BOLD}================================{Colors.RESET}\n")

    # Test 1: Configuration
    config_ok = await test_configuration()

    if not config_ok:
        print_error("\nConfiguration incomplete - cannot proceed with tests")
        print_info("Please set all required environment variables in .env file")
        return

    # Run diagnostic tests
    await diagnose_permissions()

    print(f"\n{Colors.BOLD}{Colors.GREEN}Test suite completed{Colors.RESET}\n")


if __name__ == "__main__":
    asyncio.run(main())
