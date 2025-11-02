"""Morph API client for Fast Apply code merging."""

import os
import requests
from typing import Optional


class MorphAPIError(Exception):
    """Custom exception for Morph API errors."""
    pass


def merge_code(instruction: str, initial_code: str, update_block: str) -> str:
    """
    Merge code using Morph's Fast Apply API.

    Args:
        instruction: Natural language description of the changes
        initial_code: Current file contents
        update_block: Fast Apply format update with '// ... existing code ...' markers

    Returns:
        Merged code as a string

    Raises:
        MorphAPIError: If API call fails or returns invalid response
    """
    api_key = os.getenv("MORPH_API_KEY")
    base_url = os.getenv("MORPH_BASE_URL", "https://api.morphllm.com/v1")

    if not api_key:
        raise MorphAPIError(
            "MORPH_API_KEY not found in environment. "
            "Please set it in your .env file or environment variables."
        )

    # Construct the user message content in Morph Fast Apply format
    content = (
        f"<instruction>{instruction}</instruction>\n"
        f"<code>{initial_code}</code>\n"
        f"<update>{update_block}</update>"
    )

    # Prepare API request
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "morph-v3-fast",
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise MorphAPIError("Request to Morph API timed out after 30 seconds")
    except requests.exceptions.RequestException as e:
        error_msg = f"Morph API request failed: {str(e)}"
        try:
            error_detail = response.json()
            error_msg += f"\nAPI response: {error_detail}"
        except:
            error_msg += f"\nStatus code: {response.status_code}"
        raise MorphAPIError(error_msg)

    # Parse response
    try:
        data = response.json()
        merged_code = data["choices"][0]["message"]["content"]

        if not merged_code or not merged_code.strip():
            raise MorphAPIError(
                "Morph API returned empty content. "
                f"Full response: {data}"
            )

        return merged_code

    except (KeyError, IndexError) as e:
        raise MorphAPIError(
            f"Unexpected Morph API response format: {str(e)}\n"
            f"Response: {data if 'data' in locals() else 'Unable to parse'}"
        )
