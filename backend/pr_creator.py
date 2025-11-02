"""Direct PR creation helper (workaround for MCP issues)."""

import os
import time
from github import Github
from dotenv import load_dotenv

load_dotenv()

class PRCreator:
    """Helper class to create GitHub PRs directly."""

    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.g = Github(self.github_token) if self.github_token else None

    def create_pr(
        self,
        repo_fullname: str,
        instruction: str,
        update_block: str,
        file_path: str,
        base_branch: str = "main"
    ) -> dict:
        """
        Create a GitHub PR with code changes.

        Args:
            repo_fullname: Repository in format "owner/repo"
            instruction: Description of the change
            update_block: Code diff or new content
            file_path: Path to file to modify
            base_branch: Base branch to merge into

        Returns:
            dict with pr_url, pr_number, branch_name
        """
        if not self.g:
            raise ValueError("GITHUB_TOKEN not set")

        try:
            repo = self.g.get_repo(repo_fullname)

            # Create branch name
            timestamp = int(time.time())
            branch_name = f"northstar/exp-{timestamp}"

            # Get base branch
            base = repo.get_branch(base_branch)

            # Create new branch
            repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=base.commit.sha
            )

            # Update or create file
            try:
                # Try to get existing file
                file = repo.get_contents(file_path, ref=branch_name)

                # For simplicity, just append the update_block
                # In production, you'd parse the diff and apply it properly
                current_content = file.decoded_content.decode('utf-8')
                new_content = current_content + "\n" + update_block

                repo.update_file(
                    path=file_path,
                    message=f"feat: {instruction}",
                    content=new_content,
                    sha=file.sha,
                    branch=branch_name
                )
            except:
                # File doesn't exist, create it
                repo.create_file(
                    path=file_path,
                    message=f"feat: {instruction}",
                    content=update_block,
                    branch=branch_name
                )

            # Create PR
            pr = repo.create_pull(
                title=f"Northstar: {instruction}",
                body=f"""🤖 **Northstar Experiment**

## Description
{instruction}

## Code Changes
```
{update_block[:500]}
```

---
Generated with Northstar AI experimentation platform
""",
                head=branch_name,
                base=base_branch
            )

            return {
                "pr_url": pr.html_url,
                "pr_number": pr.number,
                "branch_name": branch_name,
                "status": "success"
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "pr_url": None
            }
