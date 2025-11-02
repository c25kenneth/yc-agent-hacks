"""Git operations for cloning, branching, committing, and pushing."""

import os
import tempfile
import shutil
from pathlib import Path
from git import Repo, GitCommandError


def clone_repo(repo_fullname: str) -> Path:
    """
    Clone a GitHub repository to a temporary directory.

    Args:
        repo_fullname: Repository in format 'owner/repo'

    Returns:
        Path to the cloned repository

    Raises:
        Exception: If clone fails
    """
    temp_dir = tempfile.mkdtemp(prefix="northstar_")
    repo_path = Path(temp_dir)

    clone_url = f"https://github.com/{repo_fullname}.git"

    try:
        Repo.clone_from(clone_url, repo_path)
        return repo_path
    except GitCommandError as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise Exception(
            f"Failed to clone repository '{repo_fullname}'.\n"
            f"Error: {str(e)}\n"
            f"Hint: Verify the repository exists and is accessible."
        )


def ensure_branch(repo: Repo, base_branch: str, new_branch: str) -> str:
    """
    Create a unique branch name, appending -v2, -v3, etc. if branch exists.

    Args:
        repo: GitPython Repo object
        base_branch: Base branch to branch from (e.g., 'main')
        new_branch: Desired new branch name

    Returns:
        Final unique branch name that was created
    """
    # Ensure we're on the base branch
    try:
        repo.git.checkout(base_branch)
    except GitCommandError:
        raise Exception(
            f"Failed to checkout base branch '{base_branch}'.\n"
            f"Hint: Verify that '{base_branch}' exists in the repository."
        )

    # Find unique branch name
    final_branch = new_branch
    counter = 2

    while True:
        try:
            # Check if branch exists locally
            repo.git.rev_parse("--verify", final_branch)
            # Branch exists, try next version
            final_branch = f"{new_branch}-v{counter}"
            counter += 1
        except GitCommandError:
            # Branch doesn't exist, we can use it
            break

    # Create and checkout the new branch
    repo.git.checkout("-b", final_branch)

    return final_branch


def create_commit_and_push(repo: Repo, branch: str, message: str) -> None:
    """
    Stage all changes, create a commit, and push to remote.

    Args:
        repo: GitPython Repo object
        branch: Branch name to push
        message: Commit message

    Raises:
        Exception: If commit or push fails
    """
    try:
        # Stage all changes
        repo.git.add("-A")

        # Check if there are changes to commit
        if not repo.is_dirty() and not repo.untracked_files:
            return

        # Create commit
        repo.index.commit(message)

        # Push to remote
        origin = repo.remote("origin")
        origin.push(branch)

    except GitCommandError as e:
        raise Exception(
            f"Failed to commit and push changes.\n"
            f"Error: {str(e)}\n"
            f"Hint: Ensure you have write access to the repository."
        )


def cleanup_repo(repo_path: Path) -> None:
    """
    Clean up cloned repository directory.

    Args:
        repo_path: Path to repository to remove
    """
    try:
        shutil.rmtree(repo_path, ignore_errors=True)
    except Exception:
        pass  # Best effort cleanup
