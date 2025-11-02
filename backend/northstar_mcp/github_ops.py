"""GitHub operations for creating pull requests."""

import os
from github import Github, GithubException


def open_pr(
    repo_fullname: str,
    head_branch: str,
    base_branch: str,
    title: str,
    body: str
) -> str:
    """
    Create a pull request on GitHub, or return existing PR URL if one exists.

    Args:
        repo_fullname: Repository in format 'owner/repo'
        head_branch: Source branch (the new changes)
        base_branch: Target branch (usually 'main')
        title: PR title
        body: PR description

    Returns:
        URL of the created or existing pull request

    Raises:
        Exception: If PR creation fails
    """
    github_token = os.getenv("GITHUB_TOKEN")

    if not github_token:
        raise Exception(
            "GITHUB_TOKEN not found in environment.\n"
            "Hint: Set it in your .env file or environment variables."
        )

    try:
        g = Github(github_token)
        repo = g.get_repo(repo_fullname)

        # Check if PR already exists for this branch
        existing_prs = repo.get_pulls(state="open", head=f"{repo.owner.login}:{head_branch}")

        for pr in existing_prs:
            return pr.html_url

        # Create new PR
        pr = repo.create_pull(
            title=title,
            body=body,
            base=base_branch,
            head=head_branch
        )

        return pr.html_url

    except GithubException as e:
        error_msg = f"GitHub API error: {e.data.get('message', str(e))}"

        if e.status == 401:
            error_msg += "\nHint: Your GITHUB_TOKEN may be invalid or expired."
        elif e.status == 404:
            error_msg += f"\nHint: Repository '{repo_fullname}' not found or you don't have access."
        elif e.status == 422:
            error_msg += "\nHint: Check that base and head branches are different and exist."

        raise Exception(error_msg)
    except Exception as e:
        raise Exception(f"Failed to create pull request: {str(e)}")
