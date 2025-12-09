"""
Additional endpoints for Jenkins/GitHub integration.
Add these to main.py after line 473.
"""

# New Pydantic models for Jenkins integration

class JenkinsConnectionRequest(BaseModel):
    """Jenkins connection configuration."""
    jenkins_url: str = "http://54.87.173.145:8080"
    username: str = "admin"
    password: str = "admin"


class GitHubConnectionRequest(BaseModel):
    """GitHub connection configuration."""
    token: str
    username: Optional[str] = None


class MigrateJobRequest(BaseModel):
    """Request to migrate a Jenkins job to GitHub."""
    jenkins_url: str = "http://54.87.173.145:8080"
    jenkins_username: str = "admin"
    jenkins_password: str = "admin"
    job_name: str
    github_token: str
    github_repo_name: Optional[str] = None
    create_repo: bool = True
    private_repo: bool = False


# New endpoints

@app.get("/jenkins/test")
async def test_jenkins_connection(
    jenkins_url: str = "http://54.87.173.145:8080",
    username: str = "admin",
    password: str = "admin"
):
    """Test connection to Jenkins server."""
    try:
        client = JenkinsClient(jenkins_url, username, password)
        result = client.test_connection()
        return result
    except Exception as e:
        migration_agent.logger.error(f"Error testing Jenkins connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jenkins/jobs")
async def list_jenkins_jobs(
    jenkins_url: str = "http://54.87.173.145:8080",
    username: str = "admin",
    password: str = "admin"
):
    """
    List all Jenkins jobs.

    Query parameters:
    - jenkins_url: Jenkins server URL (default: http://54.87.173.145:8080)
    - username: Jenkins username (default: admin)
    - password: Jenkins password/token (default: admin)
    """
    try:
        client = JenkinsClient(jenkins_url, username, password)
        jobs = client.get_jobs()

        return {
            'success': True,
            'jenkins_url': jenkins_url,
            'jobs_count': len(jobs),
            'jobs': jobs
        }
    except Exception as e:
        migration_agent.logger.error(f"Error listing Jenkins jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jenkins/jobs/{job_name}")
async def get_jenkins_job_details(
    job_name: str,
    jenkins_url: str = "http://54.87.173.145:8080",
    username: str = "admin",
    password: str = "admin"
):
    """
    Get detailed information about a specific Jenkins job.

    Path parameters:
    - job_name: Name of the Jenkins job

    Query parameters:
    - jenkins_url: Jenkins server URL
    - username: Jenkins username
    - password: Jenkins password/token
    """
    try:
        client = JenkinsClient(jenkins_url, username, password)
        job_details = client.get_job_details(job_name)

        return {
            'success': True,
            'job': job_details
        }
    except Exception as e:
        migration_agent.logger.error(f"Error getting job details: {e}")
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/jenkins/migrate-job")
async def migrate_jenkins_job(request: MigrateJobRequest):
    """
    Migrate a Jenkins job to GitHub Actions.

    This endpoint:
    1. Fetches the Jenkins job configuration
    2. Extracts the pipeline script
    3. Converts it to GitHub Actions workflow
    4. Optionally creates a GitHub repository
    5. Creates the workflow file in the repository
    """
    try:
        # Step 1: Connect to Jenkins and fetch job
        jenkins_client = JenkinsClient(
            request.jenkins_url,
            request.jenkins_username,
            request.jenkins_password
        )

        migration_agent.logger.info(f"Fetching Jenkins job: {request.job_name}")
        job_details = jenkins_client.get_job_details(request.job_name)

        if not job_details.get('pipeline_script'):
            raise HTTPException(
                status_code=400,
                detail=f"No pipeline script found in job '{request.job_name}'. Only Pipeline jobs are supported."
            )

        # Step 2: Convert pipeline to GitHub Actions
        migration_agent.logger.info(f"Converting pipeline to GitHub Actions")
        migration_result = await migration_agent.migrate_pipeline(
            job_details['pipeline_script'],
            request.job_name
        )

        if not migration_result.get('success'):
            raise HTTPException(
                status_code=400,
                detail=migration_result.get('error', 'Migration failed')
            )

        # Step 3: Connect to GitHub
        github_client = GitHubClient(request.github_token)

        # Step 4: Create or use repository
        repo_name = request.github_repo_name or request.job_name.lower().replace(' ', '-')
        repo_info = None

        if request.create_repo:
            migration_agent.logger.info(f"Creating GitHub repository: {repo_name}")
            repo_info = github_client.create_repository(
                repo_name,
                job_details.get('description', ''),
                request.private_repo
            )
        else:
            repo_info = github_client.get_repository(repo_name)
            if not repo_info:
                raise HTTPException(
                    status_code=404,
                    detail=f"Repository '{repo_name}' not found and create_repo=False"
                )

        # Step 5: Create workflow file
        migration_agent.logger.info(f"Creating workflow file in repository")
        workflow_name = f"{request.job_name.lower().replace(' ', '-')}.yml"
        workflow_info = github_client.create_workflow_file(
            repo_name,
            migration_result['github_workflow'],
            workflow_name
        )

        # Step 6: Return comprehensive result
        return {
            'success': True,
            'jenkins_job': {
                'name': request.job_name,
                'url': job_details['url']
            },
            'github_repository': {
                'name': repo_info['name'],
                'url': repo_info['url'],
                'created': repo_info.get('created', False)
            },
            'github_workflow': {
                'name': workflow_name,
                'path': workflow_info['path'],
                'url': workflow_info['url'],
                'created': workflow_info.get('created', False)
            },
            'migration_report': migration_result['migration_report'],
            'warnings': migration_result.get('warnings', []),
            'next_steps': [
                f"1. Review the workflow at: {workflow_info['url']}",
                f"2. Configure repository secrets if needed",
                f"3. Push code to trigger the workflow",
                f"4. Monitor workflow runs at: {repo_info['url']}/actions"
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        migration_agent.logger.error(f"Error migrating Jenkins job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/github/test")
async def test_github_connection(token: str):
    """Test connection to GitHub API."""
    try:
        client = GitHubClient(token)
        result = client.test_connection()
        return result
    except Exception as e:
        migration_agent.logger.error(f"Error testing GitHub connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper endpoint for testing
@app.get("/integration/test")
async def test_full_integration(
    jenkins_url: str = "http://54.87.173.145:8080",
    jenkins_username: str = "admin",
    jenkins_password: str = "admin",
    github_token: Optional[str] = None
):
    """
    Test both Jenkins and GitHub connections.
    Returns status of both integrations.
    """
    result = {
        'jenkins': {},
        'github': {}
    }

    try:
        jenkins_client = JenkinsClient(jenkins_url, jenkins_username, jenkins_password)
        result['jenkins'] = jenkins_client.test_connection()
    except Exception as e:
        result['jenkins'] = {'connected': False, 'error': str(e)}

    if github_token:
        try:
            github_client = GitHubClient(github_token)
            result['github'] = github_client.test_connection()
        except Exception as e:
            result['github'] = {'connected': False, 'error': str(e)}
    else:
        result['github'] = {'connected': False, 'error': 'No token provided'}

    return result
