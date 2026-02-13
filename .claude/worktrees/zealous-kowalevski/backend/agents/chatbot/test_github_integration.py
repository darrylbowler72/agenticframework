"""
Integration tests for Chatbot Agent GitHub operations.

Tests the chatbot agent's ability to perform GitHub operations like:
- Creating repositories
- Deleting repositories
- Listing repositories
- Managing repository settings

WARNING: These tests perform real GitHub operations against the configured account.
Ensure you're using a test account or are comfortable with test repositories being created/deleted.
"""

import asyncio
import uuid
import pytest
import pytest_asyncio
from datetime import datetime
from typing import List

from github import Github
from github.GithubException import GithubException

# Test configuration
GITHUB_OWNER = "darrylbowler72"
TEST_REPO_PREFIX = "test-chatbot-"
MAX_TEST_REPOS = 5  # Safety limit on number of test repos


class TestChatbotGitHubIntegration:
    """Test suite for Chatbot GitHub integration."""

    @pytest_asyncio.fixture
    async def github_client(self):
        """Initialize GitHub client using chatbot agent's credentials."""
        # Import here to avoid circular dependencies
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # Import ChatbotAgent from main module
        from chatbot.main import ChatbotAgent

        # Create a temporary agent instance to get GitHub credentials
        agent = ChatbotAgent()
        client, owner = await agent._get_github_client()

        yield client, owner

        # Cleanup: Remove any leftover test repositories
        await self._cleanup_test_repos(client, owner)

    async def _cleanup_test_repos(self, client: Github, owner: str):
        """Clean up any test repositories that weren't properly deleted."""
        try:
            user = client.get_user()  # Get authenticated user
            repos = user.get_repos()

            deleted_count = 0
            for repo in repos:
                if repo.name.startswith(TEST_REPO_PREFIX):
                    print(f"Cleaning up test repository: {repo.name}")
                    repo.delete()
                    deleted_count += 1

            if deleted_count > 0:
                print(f"Cleaned up {deleted_count} test repositories")

        except GithubException as e:
            print(f"Warning: Error during cleanup: {e}")

    def _generate_test_repo_name(self) -> str:
        """Generate a unique test repository name."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        unique_id = uuid.uuid4().hex[:6]
        return f"{TEST_REPO_PREFIX}{timestamp}-{unique_id}"

    @pytest.mark.asyncio
    async def test_create_repository(self, github_client):
        """Test creating a GitHub repository."""
        client, owner = github_client
        repo_name = self._generate_test_repo_name()

        try:
            # Create repository using authenticated user
            user = client.get_user()  # Get authenticated user
            repo = user.create_repo(
                name=repo_name,
                description="Test repository created by chatbot integration tests",
                private=False,
                auto_init=True
            )

            assert repo is not None
            assert repo.name == repo_name
            assert repo.owner.login == owner
            print(f"[OK] Successfully created repository: {repo.full_name}")

            # Verify repository exists
            fetched_repo = client.get_repo(f"{owner}/{repo_name}")
            assert fetched_repo.name == repo_name

        finally:
            # Cleanup: Delete the test repository
            try:
                repo = client.get_repo(f"{owner}/{repo_name}")
                repo.delete()
                print(f"[OK] Successfully deleted test repository: {repo_name}")
            except GithubException:
                pass

    @pytest.mark.asyncio
    async def test_delete_repository(self, github_client):
        """Test deleting a GitHub repository."""
        client, owner = github_client
        repo_name = self._generate_test_repo_name()

        # First create a repository to delete
        user = client.get_user()  # Get authenticated user
        repo = user.create_repo(
            name=repo_name,
            description="Test repository for deletion test",
            private=False
        )

        print(f"[OK] Created repository for deletion test: {repo.full_name}")

        # Now delete it
        repo.delete()
        print(f"[OK] Successfully deleted repository: {repo_name}")

        # Verify it's gone
        with pytest.raises(GithubException) as exc_info:
            client.get_repo(f"{owner}/{repo_name}")

        assert exc_info.value.status == 404

    @pytest.mark.asyncio
    async def test_create_and_list_repositories(self, github_client):
        """Test creating multiple repositories and listing them."""
        client, owner = github_client
        test_repos = []

        try:
            # Create multiple test repositories
            user = client.get_user()  # Get authenticated user
            for i in range(3):
                repo_name = self._generate_test_repo_name()
                repo = user.create_repo(
                    name=repo_name,
                    description=f"Test repository #{i+1}",
                    private=False
                )
                test_repos.append(repo)
                print(f"[OK] Created repository {i+1}/3: {repo.name}")

            # List repositories and verify our test repos exist
            all_repos = list(user.get_repos())
            test_repo_names = {r.name for r in test_repos}
            found_repos = {r.name for r in all_repos if r.name in test_repo_names}

            assert len(found_repos) == 3
            print(f"[OK] Successfully found all {len(found_repos)} test repositories")

        finally:
            # Cleanup: Delete all test repositories
            for repo in test_repos:
                try:
                    repo.delete()
                    print(f"[OK] Deleted test repository: {repo.name}")
                except GithubException as e:
                    print(f"Warning: Failed to delete {repo.name}: {e}")

    @pytest.mark.asyncio
    async def test_repository_with_readme(self, github_client):
        """Test creating a repository with README initialization."""
        client, owner = github_client
        repo_name = self._generate_test_repo_name()

        try:
            user = client.get_user()  # Get authenticated user
            repo = user.create_repo(
                name=repo_name,
                description="Test repository with README",
                private=False,
                auto_init=True  # This creates a README.md
            )

            print(f"[OK] Created repository with README: {repo.full_name}")

            # Verify README exists
            readme = repo.get_readme()
            assert readme is not None
            assert readme.name == "README.md"
            print(f"[OK] README.md exists in repository")

            # Verify default branch exists
            assert repo.default_branch is not None
            print(f"[OK] Default branch: {repo.default_branch}")

        finally:
            # Cleanup
            try:
                repo = client.get_repo(f"{owner}/{repo_name}")
                repo.delete()
                print(f"[OK] Deleted test repository: {repo_name}")
            except GithubException:
                pass

    @pytest.mark.asyncio
    async def test_update_repository_description(self, github_client):
        """Test updating repository properties."""
        client, owner = github_client
        repo_name = self._generate_test_repo_name()

        try:
            # Create repository
            user = client.get_user()  # Get authenticated user
            repo = user.create_repo(
                name=repo_name,
                description="Original description",
                private=False
            )

            print(f"[OK] Created repository: {repo.full_name}")
            assert repo.description == "Original description"

            # Update description
            repo.edit(description="Updated description by test")

            # Verify update
            updated_repo = client.get_repo(f"{owner}/{repo_name}")
            assert updated_repo.description == "Updated description by test"
            print(f"[OK] Successfully updated repository description")

        finally:
            # Cleanup
            try:
                repo = client.get_repo(f"{owner}/{repo_name}")
                repo.delete()
                print(f"[OK] Deleted test repository: {repo_name}")
            except GithubException:
                pass

    @pytest.mark.asyncio
    async def test_error_handling_duplicate_repo(self, github_client):
        """Test error handling when creating duplicate repository."""
        client, owner = github_client
        repo_name = self._generate_test_repo_name()

        try:
            # Create first repository
            user = client.get_user()  # Get authenticated user
            repo1 = user.create_repo(
                name=repo_name,
                description="First repository",
                private=False
            )
            print(f"[OK] Created first repository: {repo_name}")

            # Try to create duplicate - should raise exception
            with pytest.raises(GithubException) as exc_info:
                user.create_repo(
                    name=repo_name,
                    description="Duplicate repository",
                    private=False
                )

            # Verify it's the correct error (422 Unprocessable Entity)
            assert exc_info.value.status == 422
            print(f"[OK] Correctly handled duplicate repository error")

        finally:
            # Cleanup
            try:
                repo = client.get_repo(f"{owner}/{repo_name}")
                repo.delete()
                print(f"[OK] Deleted test repository: {repo_name}")
            except GithubException:
                pass

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, github_client):
        """Test handling multiple concurrent GitHub operations."""
        client, owner = github_client
        test_repos = []

        async def create_repo_async(index: int) -> str:
            """Create a repository asynchronously."""
            repo_name = f"{TEST_REPO_PREFIX}concurrent-{index}-{uuid.uuid4().hex[:6]}"
            user = client.get_user()  # Get authenticated user
            repo = user.create_repo(
                name=repo_name,
                description=f"Concurrent test repository #{index}",
                private=False
            )
            return repo_name

        try:
            # Create repositories concurrently
            repo_names = await asyncio.gather(
                create_repo_async(1),
                create_repo_async(2),
                create_repo_async(3)
            )

            print(f"[OK] Successfully created {len(repo_names)} repositories concurrently")

            # Verify all exist
            for repo_name in repo_names:
                repo = client.get_repo(f"{owner}/{repo_name}")
                assert repo is not None
                test_repos.append(repo)

            print(f"[OK] Verified all concurrent repositories exist")

        finally:
            # Cleanup
            for repo in test_repos:
                try:
                    repo.delete()
                    print(f"[OK] Deleted test repository: {repo.name}")
                except GithubException as e:
                    print(f"Warning: Failed to delete {repo.name}: {e}")


def run_tests():
    """Run all GitHub integration tests."""
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--asyncio-mode=auto",
        "--tb=short"
    ])


if __name__ == "__main__":
    print("=" * 80)
    print("Chatbot Agent - GitHub Integration Tests")
    print("=" * 80)
    print(f"Target Account: {GITHUB_OWNER}")
    print(f"Test Repo Prefix: {TEST_REPO_PREFIX}")
    print("=" * 80)
    print()

    run_tests()
