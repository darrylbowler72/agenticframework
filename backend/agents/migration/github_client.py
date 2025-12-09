"""
GitHub Client for creating repositories and workflows.
"""

import requests
import base64
from typing import Dict, Optional


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, token: str, username: str = None):
        """
        Initialize GitHub client.

        Args:
            token: GitHub personal access token
            username: GitHub username (optional, will be fetched if not provided)
        """
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.username = username or self._get_authenticated_user()

    def _get_authenticated_user(self) -> str:
        """Get the authenticated user's username."""
        try:
            response = self.session.get(f"{self.base_url}/user", timeout=10)
            response.raise_for_status()
            return response.json().get('login')
        except Exception as e:
            raise Exception(f"Failed to get authenticated user: {str(e)}")

    def create_repository(self, repo_name: str, description: str = "", private: bool = False) -> Dict:
        """
        Create a new GitHub repository.

        Args:
            repo_name: Name of the repository
            description: Repository description
            private: Whether the repository should be private

        Returns:
            Repository details
        """
        try:
            data = {
                "name": repo_name,
                "description": description or f"Migrated from Jenkins: {repo_name}",
                "private": private,
                "auto_init": True,  # Initialize with README
                "has_issues": True,
                "has_projects": True,
                "has_wiki": True
            }

            response = self.session.post(
                f"{self.base_url}/user/repos",
                json=data,
                timeout=10
            )
            response.raise_for_status()

            repo_data = response.json()

            return {
                'name': repo_data['name'],
                'full_name': repo_data['full_name'],
                'url': repo_data['html_url'],
                'clone_url': repo_data['clone_url'],
                'created': True
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 422:
                # Repository already exists
                return {
                    'name': repo_name,
                    'full_name': f"{self.username}/{repo_name}",
                    'url': f"https://github.com/{self.username}/{repo_name}",
                    'clone_url': f"https://github.com/{self.username}/{repo_name}.git",
                    'created': False,
                    'exists': True
                }
            raise Exception(f"Failed to create repository: {str(e)}")

        except Exception as e:
            raise Exception(f"Failed to create repository: {str(e)}")

    def create_workflow_file(self, repo_name: str, workflow_content: str,
                           workflow_name: str = "ci.yml") -> Dict:
        """
        Create a GitHub Actions workflow file in the repository.

        Args:
            repo_name: Name of the repository
            workflow_content: YAML content of the workflow
            workflow_name: Name of the workflow file (default: ci.yml)

        Returns:
            File creation details
        """
        try:
            # Encode content to base64
            content_bytes = workflow_content.encode('utf-8')
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')

            # Create .github/workflows directory structure
            workflow_path = f".github/workflows/{workflow_name}"

            data = {
                "message": f"Add GitHub Actions workflow: {workflow_name}",
                "content": content_base64,
                "branch": "main"
            }

            url = f"{self.base_url}/repos/{self.username}/{repo_name}/contents/{workflow_path}"
            response = self.session.put(url, json=data, timeout=10)
            response.raise_for_status()

            file_data = response.json()

            return {
                'path': workflow_path,
                'url': file_data['content']['html_url'],
                'sha': file_data['content']['sha'],
                'created': True
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 422:
                # File already exists
                return {
                    'path': workflow_path,
                    'url': f"https://github.com/{self.username}/{repo_name}/blob/main/{workflow_path}",
                    'created': False,
                    'exists': True
                }
            raise Exception(f"Failed to create workflow file: {str(e)}")

        except Exception as e:
            raise Exception(f"Failed to create workflow file: {str(e)}")

    def get_repository(self, repo_name: str) -> Optional[Dict]:
        """
        Get repository details.

        Args:
            repo_name: Name of the repository

        Returns:
            Repository details or None if not found
        """
        try:
            response = self.session.get(
                f"{self.base_url}/repos/{self.username}/{repo_name}",
                timeout=10
            )

            if response.status_code == 404:
                return None

            response.raise_for_status()
            repo_data = response.json()

            return {
                'name': repo_data['name'],
                'full_name': repo_data['full_name'],
                'url': repo_data['html_url'],
                'description': repo_data['description'],
                'private': repo_data['private'],
                'created_at': repo_data['created_at']
            }

        except Exception as e:
            raise Exception(f"Failed to get repository: {str(e)}")

    def test_connection(self) -> Dict:
        """
        Test connection to GitHub API.

        Returns:
            Dictionary with connection status
        """
        try:
            response = self.session.get(f"{self.base_url}/user", timeout=5)
            response.raise_for_status()

            user_data = response.json()

            return {
                'connected': True,
                'username': user_data.get('login'),
                'name': user_data.get('name'),
                'email': user_data.get('email'),
                'public_repos': user_data.get('public_repos'),
                'private_repos': user_data.get('total_private_repos')
            }

        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }
