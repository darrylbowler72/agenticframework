"""
Migration Agent - Jenkins to GitHub Actions Converter

Converts Jenkins pipelines to GitHub Actions workflows.
"""

import os
import re
import yaml
import json
import boto3
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.agent_base import BaseAgent
from common.version import __version__
from migration.jenkins_client import JenkinsClient
from migration.github_client import GitHubClient

app = FastAPI(
    title="Migration Agent",
    description="Converts Jenkins pipelines to GitHub Actions workflows and integrates with Jenkins/GitHub",
    version="1.0.5"
)


class MigrationRequest(BaseModel):
    """Migration request model."""
    jenkinsfile_content: str
    project_name: str
    repository_url: Optional[str] = None
    options: Optional[Dict[str, Any]] = {}


class MigrationResponse(BaseModel):
    """Migration response model."""
    github_workflow: str
    migration_report: Dict[str, Any]
    warnings: List[str]
    success: bool


class AnalyzeRequest(BaseModel):
    """Analysis request model."""
    jenkinsfile_content: str


class MigrationAgent(BaseAgent):
    """Agent for migrating Jenkins pipelines to GitHub Actions."""

    def __init__(self):
        super().__init__(agent_name="migration")

        # Jenkins to GitHub Actions step mappings
        self.step_mappings = {
            'checkout scm': 'actions/checkout@v4',
            'git': 'actions/checkout@v4',
            'sh': 'run',
            'bat': 'run',
            'echo': 'run',
            'junit': 'actions/upload-artifact@v3',
            'archiveArtifacts': 'actions/upload-artifact@v3',
            'publishHTML': 'actions/upload-artifact@v3',
        }

        # Jenkins plugins to GitHub Actions mappings
        self.plugin_mappings = {
            'docker': 'docker/build-push-action@v5',
            'kubernetes': 'azure/k8s-deploy@v4',
            'aws': 'aws-actions/configure-aws-credentials@v4',
            'sonarqube': 'SonarSource/sonarcloud-github-action@master',
            'slack': 'slackapi/slack-github-action@v1',
        }

    async def process_task(self, task_data: Dict) -> Dict:
        """Process migration task."""
        jenkinsfile = task_data.get('jenkinsfile_content', '')
        project_name = task_data.get('project_name', 'project')

        return await self.migrate_pipeline(jenkinsfile, project_name)

    def parse_jenkinsfile(self, jenkinsfile: str) -> Dict[str, Any]:
        """
        Parse Jenkinsfile and extract pipeline structure.
        Supports both Declarative and Scripted pipelines.
        """
        pipeline_data = {
            'type': None,
            'agent': 'ubuntu-latest',
            'stages': [],
            'environment': {},
            'triggers': [],
            'post_actions': {},
            'tools': []
        }

        # Detect pipeline type
        if 'pipeline {' in jenkinsfile:
            pipeline_data['type'] = 'declarative'
            pipeline_data = self._parse_declarative(jenkinsfile, pipeline_data)
        elif 'node' in jenkinsfile or 'stage' in jenkinsfile:
            pipeline_data['type'] = 'scripted'
            pipeline_data = self._parse_scripted(jenkinsfile, pipeline_data)
        else:
            pipeline_data['type'] = 'unknown'

        return pipeline_data

    def _parse_declarative(self, jenkinsfile: str, pipeline_data: Dict) -> Dict:
        """Parse Declarative Pipeline syntax."""

        # Extract agent
        agent_match = re.search(r'agent\s+{\s*label\s+["\']([^"\']+)["\']', jenkinsfile)
        if not agent_match:
            agent_match = re.search(r'agent\s+["\']([^"\']+)["\']', jenkinsfile)
        if agent_match:
            agent_label = agent_match.group(1)
            if 'linux' in agent_label.lower() or 'ubuntu' in agent_label.lower():
                pipeline_data['agent'] = 'ubuntu-latest'
            elif 'windows' in agent_label.lower():
                pipeline_data['agent'] = 'windows-latest'
            elif 'macos' in agent_label.lower() or 'mac' in agent_label.lower():
                pipeline_data['agent'] = 'macos-latest'

        # Extract environment variables
        env_block = re.search(r'environment\s*{([^}]+)}', jenkinsfile, re.DOTALL)
        if env_block:
            env_content = env_block.group(1)
            for line in env_content.strip().split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    pipeline_data['environment'][key] = value

        # Extract stages
        stages_block = re.search(r'stages\s*{(.*)}', jenkinsfile, re.DOTALL)
        if stages_block:
            stages_content = stages_block.group(1)

            # Find all stage blocks
            stage_pattern = r'stage\s*\(["\']([^"\']+)["\']\)\s*{([^}]+(?:{[^}]+}[^}]+)*?)}'
            for match in re.finditer(stage_pattern, stages_content, re.DOTALL):
                stage_name = match.group(1)
                stage_content = match.group(2)

                steps = []
                # Extract steps from stage
                steps_block = re.search(r'steps\s*{([^}]+(?:{[^}]+}[^}]+)*?)}', stage_content, re.DOTALL)
                if steps_block:
                    steps_content = steps_block.group(1)

                    # Parse individual steps
                    for line in steps_content.strip().split('\n'):
                        line = line.strip()
                        if line and not line.startswith('//'):
                            steps.append(line)

                pipeline_data['stages'].append({
                    'name': stage_name,
                    'steps': steps
                })

        # Extract triggers
        if 'cron' in jenkinsfile:
            cron_match = re.search(r'cron\s*\(["\']([^"\']+)["\']\)', jenkinsfile)
            if cron_match:
                pipeline_data['triggers'].append({
                    'type': 'cron',
                    'value': cron_match.group(1)
                })

        if 'pollSCM' in jenkinsfile:
            pipeline_data['triggers'].append({'type': 'pollSCM'})

        return pipeline_data

    def _parse_scripted(self, jenkinsfile: str, pipeline_data: Dict) -> Dict:
        """Parse Scripted Pipeline syntax."""

        # Extract node label
        node_match = re.search(r'node\s*\(["\']([^"\']+)["\']\)', jenkinsfile)
        if node_match:
            agent_label = node_match.group(1)
            if 'linux' in agent_label.lower():
                pipeline_data['agent'] = 'ubuntu-latest'
            elif 'windows' in agent_label.lower():
                pipeline_data['agent'] = 'windows-latest'

        # Extract stages
        stage_pattern = r'stage\s*\(["\']([^"\']+)["\']\)\s*{([^}]+)}'
        for match in re.finditer(stage_pattern, jenkinsfile, re.DOTALL):
            stage_name = match.group(1)
            stage_content = match.group(2)

            steps = []
            for line in stage_content.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('//') and not line.startswith('/*'):
                    steps.append(line)

            pipeline_data['stages'].append({
                'name': stage_name,
                'steps': steps
            })

        return pipeline_data

    def convert_to_github_actions(self, pipeline_data: Dict, project_name: str) -> Dict[str, Any]:
        """Convert parsed Jenkins pipeline to GitHub Actions workflow."""

        workflow = {
            'name': f'{project_name} CI/CD',
            'on': self._convert_triggers(pipeline_data['triggers']),
            'env': pipeline_data['environment'],
            'jobs': {}
        }

        # Create a job for each stage or combine into single job
        if len(pipeline_data['stages']) <= 3:
            # Single job with multiple steps
            workflow['jobs']['build'] = self._create_combined_job(pipeline_data)
        else:
            # Multiple jobs, one per stage
            for stage in pipeline_data['stages']:
                job_name = stage['name'].lower().replace(' ', '-')
                workflow['jobs'][job_name] = self._create_stage_job(stage, pipeline_data)

        return workflow

    def _convert_triggers(self, triggers: List[Dict]) -> Dict:
        """Convert Jenkins triggers to GitHub Actions triggers."""
        github_triggers = {'push': {'branches': ['main', 'develop']}}

        for trigger in triggers:
            if trigger['type'] == 'cron':
                github_triggers['schedule'] = [{'cron': trigger['value']}]
            elif trigger['type'] == 'pollSCM':
                # GitHub Actions doesn't have direct equivalent, use push trigger
                pass

        return github_triggers

    def _create_combined_job(self, pipeline_data: Dict) -> Dict:
        """Create a single GitHub Actions job combining all stages."""
        job = {
            'runs-on': pipeline_data['agent'],
            'steps': []
        }

        # Add checkout step
        job['steps'].append({
            'name': 'Checkout code',
            'uses': 'actions/checkout@v4'
        })

        # Convert each stage to steps
        for stage in pipeline_data['stages']:
            # Add stage as a comment/name
            for step in stage['steps']:
                converted_step = self._convert_step(step, stage['name'])
                if converted_step:
                    job['steps'].append(converted_step)

        return job

    def _create_stage_job(self, stage: Dict, pipeline_data: Dict) -> Dict:
        """Create a GitHub Actions job for a single stage."""
        job = {
            'runs-on': pipeline_data['agent'],
            'steps': []
        }

        # Add checkout step
        job['steps'].append({
            'name': 'Checkout code',
            'uses': 'actions/checkout@v4'
        })

        # Convert stage steps
        for step in stage['steps']:
            converted_step = self._convert_step(step, stage['name'])
            if converted_step:
                job['steps'].append(converted_step)

        return job

    def _convert_step(self, jenkins_step: str, stage_name: str) -> Optional[Dict]:
        """Convert a single Jenkins step to GitHub Actions step."""
        step = None

        # Handle sh/bat commands
        if jenkins_step.startswith('sh ') or jenkins_step.startswith('bat '):
            # Extract command
            command = re.search(r'["\']([^"\']+)["\']', jenkins_step)
            if command:
                step = {
                    'name': f'Run {stage_name} script',
                    'run': command.group(1)
                }

        # Handle echo commands
        elif jenkins_step.startswith('echo '):
            command = re.search(r'echo\s+["\']([^"\']+)["\']', jenkins_step)
            if command:
                step = {
                    'name': 'Echo message',
                    'run': f'echo "{command.group(1)}"'
                }

        # Handle checkout
        elif 'checkout' in jenkins_step.lower() or 'git' in jenkins_step.lower():
            step = {
                'name': 'Checkout code',
                'uses': 'actions/checkout@v4'
            }

        # Handle artifact archiving
        elif 'archiveArtifacts' in jenkins_step:
            artifacts_match = re.search(r'artifacts:\s*["\']([^"\']+)["\']', jenkins_step)
            if artifacts_match:
                step = {
                    'name': 'Upload artifacts',
                    'uses': 'actions/upload-artifact@v3',
                    'with': {
                        'name': 'build-artifacts',
                        'path': artifacts_match.group(1)
                    }
                }

        # Handle Docker build
        elif 'docker' in jenkins_step.lower() and 'build' in jenkins_step.lower():
            step = {
                'name': 'Build Docker image',
                'uses': 'docker/build-push-action@v5',
                'with': {
                    'context': '.',
                    'push': False,
                    'tags': '${{ github.repository }}:${{ github.sha }}'
                }
            }

        # Generic command fallback
        elif jenkins_step:
            step = {
                'name': f'Run: {jenkins_step[:50]}',
                'run': jenkins_step.strip().rstrip(';')
            }

        return step

    async def migrate_pipeline(self, jenkinsfile: str, project_name: str) -> Dict:
        """Main migration method."""
        try:
            warnings = []

            # Parse Jenkinsfile
            pipeline_data = self.parse_jenkinsfile(jenkinsfile)

            if pipeline_data['type'] == 'unknown':
                return {
                    'success': False,
                    'error': 'Unable to parse Jenkinsfile. Supported formats: Declarative and Scripted pipelines'
                }

            # Convert to GitHub Actions
            workflow = self.convert_to_github_actions(pipeline_data, project_name)

            # Generate YAML
            workflow_yaml = yaml.dump(workflow, default_flow_style=False, sort_keys=False)

            # Generate migration report
            report = {
                'source_type': 'Jenkins',
                'target_type': 'GitHub Actions',
                'pipeline_type': pipeline_data['type'],
                'stages_converted': len(pipeline_data['stages']),
                'environment_variables': len(pipeline_data['environment']),
                'triggers_converted': len(pipeline_data['triggers']),
                'timestamp': datetime.utcnow().isoformat()
            }

            # Add warnings
            if not pipeline_data['triggers']:
                warnings.append('No triggers found in Jenkinsfile. Default push trigger added.')

            if pipeline_data['type'] == 'scripted':
                warnings.append('Scripted pipeline detected. Manual review recommended for complex logic.')

            self.logger.info(f"Successfully migrated pipeline: {project_name}")

            return {
                'success': True,
                'github_workflow': workflow_yaml,
                'migration_report': report,
                'warnings': warnings
            }

        except Exception as e:
            self.logger.error(f"Migration error: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Initialize migration agent
migration_agent = MigrationAgent()


@app.get("/health")
@app.get("/dev/health")
@app.get("/migration/health")
@app.get("/dev/migration/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "migration",
        "service": "Jenkins to GitHub Actions Migration",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/migrate", response_model=MigrationResponse)
async def migrate_pipeline(request: MigrationRequest):
    """
    Migrate Jenkins pipeline to GitHub Actions.

    Takes a Jenkinsfile and converts it to a GitHub Actions workflow.
    """
    try:
        result = await migration_agent.migrate_pipeline(
            request.jenkinsfile_content,
            request.project_name
        )

        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('error', 'Migration failed'))

        return MigrationResponse(**result)

    except Exception as e:
        migration_agent.logger.error(f"Error in migration endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze")
async def analyze_pipeline(request: AnalyzeRequest):
    """
    Analyze Jenkins pipeline without converting.

    Provides information about the pipeline structure.
    """
    try:
        pipeline_data = migration_agent.parse_jenkinsfile(request.jenkinsfile_content)

        return {
            'success': True,
            'pipeline_type': pipeline_data['type'],
            'stages': [stage['name'] for stage in pipeline_data['stages']],
            'environment_variables': list(pipeline_data['environment'].keys()),
            'triggers': pipeline_data['triggers'],
            'agent': pipeline_data['agent']
        }

    except Exception as e:
        migration_agent.logger.error(f"Error in analyze endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class GitHubConnectionRequest(BaseModel):
    """GitHub connection configuration."""
    token: str
    username: Optional[str] = None


class MigrateJobRequest(BaseModel):
    """Request to migrate a Jenkins job to GitHub."""
    jenkins_url: str = "http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins"
    jenkins_username: str = "admin"
    jenkins_password: str = "admin"
    job_name: str
    github_token: str
    github_repo_name: Optional[str] = None
    create_repo: bool = True
    private_repo: bool = False


class CreateJobRequest(BaseModel):
    """Request to create a Jenkins job."""
    jenkins_url: str = "http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins"
    jenkins_username: str = "admin"
    jenkins_password: str = "admin"
    job_name: str
    config_xml: str



@app.get("/migration/jenkins/test")
@app.get("/dev/migration/jenkins/test")
async def test_jenkins_connection(
    jenkins_url: str = "http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins",
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


@app.get("/migration/jenkins/jobs")
@app.get("/dev/migration/jenkins/jobs")
async def list_jenkins_jobs(
    jenkins_url: str = "http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins",
    username: str = "admin",
    password: str = "admin"
):
    """
    List all Jenkins jobs.

    Query parameters:
    - jenkins_url: Jenkins server URL (default: http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins)
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


@app.post("/migration/jenkins/create-job")
@app.post("/dev/migration/jenkins/create-job")
async def create_jenkins_job(request: CreateJobRequest):
    """
    Create a new Jenkins job.

    Request body:
    - jenkins_url: Jenkins server URL
    - jenkins_username: Jenkins username
    - jenkins_password: Jenkins password/token
    - job_name: Name for the new job
    - config_xml: XML configuration for the job
    """
    try:
        client = JenkinsClient(request.jenkins_url, request.jenkins_username, request.jenkins_password)
        result = client.create_job(request.job_name, request.config_xml)

        if result.get('success'):
            migration_agent.logger.info(f"Created Jenkins job: {request.job_name}")
        else:
            migration_agent.logger.error(f"Failed to create Jenkins job: {result.get('error')}")

        return result
    except Exception as e:
        migration_agent.logger.error(f"Error creating Jenkins job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/migration/jenkins/jobs/{job_name}")
@app.get("/dev/migration/jenkins/jobs/{job_name}")
async def get_jenkins_job_details(
    job_name: str,
    jenkins_url: str = "http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins",
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


@app.post("/migration/jenkins/migrate-job")
@app.post("/dev/migration/jenkins/migrate-job")
async def migrate_jenkins_job(request: MigrateJobRequest):
    """
    Migrate a Jenkins job to GitHub Actions.

    This endpoint:
    1. Fetches the Jenkins job configuration
    2. Extracts the pipeline script
    3. Converts it to GitHub Actions workflow
    4. Loads GitHub token from Secrets Manager if not provided
    5. Optionally creates a GitHub repository
    6. Creates the workflow file in the repository
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

        # Step 3: Get GitHub token (from request or Secrets Manager)
        github_token = request.github_token
        if not github_token or github_token.strip() == "":
            migration_agent.logger.info("GitHub token not provided, loading from Secrets Manager")
            try:
                secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
                secret_value = secrets_client.get_secret_value(SecretId='dev-github-credentials')
                secret_data = json.loads(secret_value['SecretString'])
                github_token = secret_data.get('token', '')
                migration_agent.logger.info("Successfully loaded GitHub token from Secrets Manager")
            except Exception as e:
                migration_agent.logger.error(f"Failed to load GitHub token from Secrets Manager: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"GitHub token not provided and failed to load from Secrets Manager: {str(e)}"
                )

        # Step 4: Connect to GitHub
        github_client = GitHubClient(github_token)

        # Step 5: Create or use repository
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

        # Step 6: Create workflow file
        migration_agent.logger.info(f"Creating workflow file in repository")
        workflow_name = f"{request.job_name.lower().replace(' ', '-')}.yml"
        workflow_info = github_client.create_workflow_file(
            repo_name,
            migration_result['github_workflow'],
            workflow_name
        )

        # Step 7: Return comprehensive result
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


@app.get("/migration/github/test")
@app.get("/dev/migration/github/test")
async def test_github_connection(token: str):
    """Test connection to GitHub API."""
    try:
        client = GitHubClient(token)
        result = client.test_connection()
        return result
    except Exception as e:
        migration_agent.logger.error(f"Error testing GitHub connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/migration/integration/test")
@app.get("/dev/migration/integration/test")
async def test_full_integration(
    jenkins_url: str = "http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins",
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
