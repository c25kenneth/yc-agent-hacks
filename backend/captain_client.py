"""Captain API client for knowledge base management."""

import os
import requests
import time
from typing import Optional, Dict, Any, List
from urllib.parse import quote


class CaptainClient:
    """Client for interacting with Captain API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        organization_id: Optional[str] = None,
        base_url: str = "https://api.runcaptain.com"
    ):
        self.api_key = api_key or os.getenv("CAPTAIN_API_KEY")
        self.organization_id = organization_id or os.getenv("CAPTAIN_ORGANIZATION_ID")
        self.base_url = base_url

        if not self.api_key:
            raise ValueError("CAPTAIN_API_KEY not set")
        if not self.organization_id:
            raise ValueError("CAPTAIN_ORGANIZATION_ID not set")

    def _get_headers(self, include_org_header: bool = True) -> Dict[str, str]:
        """Get common headers for API requests."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        if include_org_header:
            headers["X-Organization-ID"] = self.organization_id
        return headers

    def create_database(self, database_name: str) -> Dict[str, Any]:
        """Create a new Captain database."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Organization-ID": self.organization_id
        }
        response = requests.post(
            f"{self.base_url}/v1/create-database",
            headers=headers,
            data={
                'organization_id': self.organization_id,
                'api_key': self.api_key,
                'database_name': database_name
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    def delete_database(self, database_name: str) -> Dict[str, Any]:
        """Delete a Captain database."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Organization-ID": self.organization_id
        }
        response = requests.post(
            f"{self.base_url}/v1/delete-database",
            headers=headers,
            data={
                'organization_id': self.organization_id,
                'api_key': self.api_key,
                'database_name': database_name
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    def list_databases(self) -> List[Dict[str, Any]]:
        """List all databases."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Organization-ID": self.organization_id
        }
        response = requests.post(
            f"{self.base_url}/v1/list-databases",
            headers=headers,
            data={
                'api_key': self.api_key,
                'organization_id': self.organization_id
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    def index_github_repo(
        self,
        database_name: str,
        repo_owner: str,
        repo_name: str,
        github_token: str,
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Index a GitHub repository into Captain.

        Note: This requires the repo to be cloned locally first,
        then we'll index the files from the local filesystem.
        """
        # For now, we'll need to implement this by cloning and indexing files
        # Captain doesn't have a direct GitHub integration yet
        raise NotImplementedError(
            "GitHub repo indexing not yet implemented. "
            "Use clone + index_local_files instead."
        )

    def check_indexing_status(self, job_id: str) -> Dict[str, Any]:
        """Check the status of an indexing job."""
        response = requests.get(
            f"{self.base_url}/v1/indexing-status/{job_id}",
            headers=self._get_headers(),
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    def wait_for_indexing(
        self,
        job_id: str,
        poll_interval: float = 3.0,
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        """
        Wait for an indexing job to complete.

        Args:
            job_id: The job ID to monitor
            poll_interval: How often to poll (seconds)
            timeout: Maximum time to wait (seconds)

        Returns:
            Final job status

        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Indexing job {job_id} did not complete within {timeout}s")

            status = self.check_indexing_status(job_id)

            if status.get("completed") or status.get("status") in ["completed", "error", "failed"]:
                return status

            time.sleep(poll_interval)

    def query(
        self,
        database_name: str,
        query: str,
        include_files: bool = True,
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """
        Query a Captain database.

        Args:
            database_name: Name of the database to query
            query: Natural language query
            include_files: Include relevant file metadata
            timeout: Request timeout in seconds

        Returns:
            Query response with answer and relevant files
        """
        response = requests.post(
            f"{self.base_url}/v1/query",
            headers=self._get_headers(),
            data={
                'query': quote(query),
                'database_name': database_name,
                'include_files': str(include_files).lower()
            },
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()

    def list_files(
        self,
        database_name: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List files in a database."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Organization-ID": self.organization_id
        }
        response = requests.post(
            f"{self.base_url}/v1/list-files",
            headers=headers,
            data={
                'organization_id': self.organization_id,
                'api_key': self.api_key,
                'database_name': database_name,
                'limit': limit,
                'offset': offset
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

    def upload_file(
        self,
        database_name: str,
        file_path: str,
        file_content: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to Captain for indexing.

        Args:
            database_name: Name of the database to upload to
            file_path: Path/name of the file (relative to repo root)
            file_content: Raw file content as bytes
            metadata: Optional metadata about the file

        Returns:
            Upload response with job ID
        """
        import base64

        # Encode file content as base64
        encoded_content = base64.b64encode(file_content).decode('utf-8')

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Organization-ID": self.organization_id
        }

        data = {
            'organization_id': self.organization_id,
            'api_key': self.api_key,
            'database_name': database_name,
            'file_path': file_path,
            'file_content': encoded_content
        }

        if metadata:
            data['metadata'] = str(metadata)

        response = requests.post(
            f"{self.base_url}/v1/upload-file",
            headers=headers,
            data=data,
            timeout=120.0
        )
        response.raise_for_status()
        return response.json()
