# Chatbot Agent - GitHub Integration Tests

This directory contains integration tests for the Chatbot Agent's GitHub operations.

## Overview

The test suite validates that the chatbot agent can perform real GitHub operations against your GitHub account, including:

- ✅ Creating repositories
- ✅ Deleting repositories
- ✅ Listing repositories
- ✅ Updating repository properties
- ✅ Error handling (duplicate repos, etc.)
- ✅ Concurrent operations

## Prerequisites

1. **AWS Credentials**: Configured to access Secrets Manager for GitHub token
2. **GitHub Token**: Stored in AWS Secrets Manager as `dev-github-credentials`
3. **Python Dependencies**: Install test requirements

```bash
pip install -r test_requirements.txt
```

## GitHub Token Permissions

Your GitHub token should have the following scopes:
- `repo` - Full control of private repositories
- `delete_repo` - Delete repositories

## Running Tests

### Run All Tests

```bash
cd backend/agents/chatbot
python test_github_integration.py
```

### Run Specific Test

```bash
pytest test_github_integration.py::TestChatbotGitHubIntegration::test_create_repository -v
```

### Run with Verbose Output

```bash
pytest test_github_integration.py -v -s
```

## Test Safety Features

The tests include several safety mechanisms:

1. **Test Repository Prefix**: All test repos use `test-chatbot-` prefix
2. **Automatic Cleanup**: Each test cleans up after itself
3. **Fixture Cleanup**: Global cleanup in test fixtures
4. **Safety Limits**: Maximum number of test repos enforced

## Test Descriptions

### test_create_repository
Creates a single repository, verifies it exists, then deletes it.

### test_delete_repository
Creates a repository, deletes it, and verifies deletion.

### test_create_and_list_repositories
Creates multiple repositories and verifies they appear in the repository list.

### test_repository_with_readme
Creates a repository with README initialization and verifies the README exists.

### test_update_repository_description
Creates a repository and updates its description.

### test_error_handling_duplicate_repo
Tests error handling when attempting to create duplicate repositories.

### test_concurrent_operations
Tests multiple concurrent GitHub operations.

## Configuration

Edit these variables in `test_github_integration.py` if needed:

```python
GITHUB_OWNER = "darrylbowler72"  # Your GitHub username
TEST_REPO_PREFIX = "test-chatbot-"  # Prefix for test repositories
MAX_TEST_REPOS = 5  # Safety limit
```

## Troubleshooting

### Authentication Errors

If you get authentication errors:
1. Verify AWS credentials are configured
2. Check Secrets Manager contains `dev-github-credentials`
3. Verify the GitHub token has required permissions

### Rate Limiting

GitHub has rate limits:
- Authenticated: 5,000 requests/hour
- Creating repos: ~1000/hour

If you hit rate limits, wait and try again later.

### Cleanup Failed Test Repos

If tests fail and leave test repositories:

```bash
# Manual cleanup
python test_github_integration.py  # Will clean up on next run
```

Or manually delete repos with prefix `test-chatbot-` from GitHub.

## CI/CD Integration

To run these tests in CI/CD:

```yaml
# Example GitHub Actions workflow
- name: Install test dependencies
  run: pip install -r backend/agents/chatbot/test_requirements.txt

- name: Run GitHub integration tests
  run: pytest backend/agents/chatbot/test_github_integration.py -v
  env:
    AWS_DEFAULT_REGION: us-east-1
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Warning

⚠️ **These tests perform real operations on GitHub!**

- Test repos are created on your actual GitHub account
- Tests attempt to clean up, but failures may leave test repos
- Ensure you're comfortable with test repos being created/deleted
- Consider using a dedicated test GitHub account

## Support

For issues or questions:
1. Check the test output for specific error messages
2. Verify AWS and GitHub credentials
3. Check GitHub's API status: https://www.githubstatus.com/
