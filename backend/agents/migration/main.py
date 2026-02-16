"""
Migration Agent - Jenkins to GitHub Actions Converter

Converts Jenkins pipelines to GitHub Actions workflows.
"""

import os
import re
import yaml
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.agent_base import BaseAgent
from common.version import __version__
from common.graphs import build_migration_graph
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

        self.graph = build_migration_graph(self)
        self.logger.info("Migration Agent initialized with LangGraph workflow")

    async def process_task(self, task_data: Dict) -> Dict:
        """Process migration task."""
        jenkinsfile = task_data.get('jenkinsfile_content', '')
        project_name = task_data.get('project_name', 'project')

        return await self.migrate_pipeline(jenkinsfile, project_name)

    async def parse_jenkinsfile_with_llm(self, jenkinsfile: str) -> Dict[str, Any]:
        """
        Use LLM to parse Jenkinsfile intelligently.
        This provides more accurate parsing than regex for complex pipelines.
        """
        prompt = f"""You are a Jenkins pipeline expert. Analyze the following Jenkinsfile and extract its structure as JSON.

Jenkinsfile:
```
{jenkinsfile}
```

Extract and return ONLY a valid JSON object with this structure:
{{
    "type": "declarative or scripted",
    "agent": "ubuntu-latest, windows-latest, or macos-latest",
    "stages": [
        {{
            "name": "stage name",
            "steps": ["list of commands or actions in this stage"]
        }}
    ],
    "environment": {{"ENV_VAR": "value"}},
    "git_url": "repository URL if present",
    "git_branch": "branch name if present",
    "triggers": [{{"type": "cron or pollSCM", "value": "cron expression if applicable"}}],
    "tools": ["java", "maven", "node", etc],
    "post_actions": {{"success": ["actions"], "failure": ["actions"]}}
}}

Be thorough - extract ALL stages, steps, commands, and configuration details."""

        try:
            response = await self.call_claude(
                prompt=prompt,
                max_tokens=4000
            )

            # Extract JSON from response (call_claude returns a string)
            content = response

            # Try to find JSON in the response
            import json
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0].strip()
            else:
                json_str = content.strip()

            pipeline_data = json.loads(json_str)
            self.logger.info(f"LLM successfully parsed pipeline with {len(pipeline_data.get('stages', []))} stages")
            return pipeline_data

        except Exception as e:
            self.logger.error(f"LLM parsing failed: {str(e)}, falling back to regex parser")
            return self.parse_jenkinsfile(jenkinsfile)

    async def generate_workflow_with_llm(self, pipeline_data: Dict, project_name: str) -> str:
        """
        Use LLM to generate optimized GitHub Actions workflow.
        This creates more idiomatic and efficient workflows than template-based generation.
        """
        prompt = f"""You are a GitHub Actions expert. Convert the following Jenkins pipeline data into an optimized GitHub Actions workflow YAML.

Pipeline Data:
```json
{json.dumps(pipeline_data, indent=2)}
```

Project Name: {project_name}

Create a GitHub Actions workflow that:
1. Uses the correct runner (ubuntu-latest, windows-latest, or macos-latest) based on the agent
2. Sets up necessary tools (Java, Maven, Node, etc.)
3. Includes proper checkout action for the repository
4. Converts all stages to jobs with dependencies
5. Uses appropriate GitHub Actions for each step
6. Includes environment variables
7. Sets up triggers (push, cron, etc.)
8. Adds artifact uploads where appropriate
9. Follows GitHub Actions best practices

IMPORTANT RULES FOR COMMANDS:
- If using ubuntu-latest or macos-latest runners, ONLY use Unix/Linux commands (./mvnw, chmod, sh, bash)
- If using windows-latest runners, ONLY use Windows commands (mvnw.cmd, bat, powershell)
- NEVER include both Unix and Windows commands in the same workflow
- When Jenkins has conditional logic like isUnix() checks, extract only the commands for the target runner
- Remove all platform-specific commands that don't match the runner

Return ONLY the complete workflow YAML, starting with 'name:'. Do not include markdown code fences or explanations."""

        try:
            response = await self.call_claude(
                prompt=prompt,
                max_tokens=4000
            )

            workflow_yaml = response.strip()

            # Remove markdown code fences if present
            if '```yaml' in workflow_yaml:
                workflow_yaml = workflow_yaml.split('```yaml')[1].split('```')[0].strip()
            elif '```' in workflow_yaml:
                workflow_yaml = workflow_yaml.split('```')[1].split('```')[0].strip()

            # Post-process: Remove platform-mismatched commands
            runner = pipeline_data.get('agent', 'ubuntu-latest')
            self.logger.info(f"PRE-CLEANUP: Workflow for runner '{runner}':\n{workflow_yaml[:500]}...")
            cleaned_workflow = self._clean_platform_commands(workflow_yaml, runner)
            self.logger.info(f"POST-CLEANUP: Cleaned workflow:\n{cleaned_workflow[:500]}...")

            self.logger.info("LLM successfully generated GitHub Actions workflow")
            return cleaned_workflow

        except Exception as e:
            self.logger.error(f"LLM workflow generation failed: {str(e)}, falling back to template-based generation")
            workflow_dict = self.convert_to_github_actions(pipeline_data, project_name)
            return yaml.dump(workflow_dict, default_flow_style=False, sort_keys=False)

    def _clean_platform_commands(self, workflow_yaml: str, runner: str) -> str:
        """
        Remove platform-mismatched commands from the workflow using YAML parsing.
        For Linux/Mac runners, remove Windows commands. For Windows runners, remove Unix commands.
        """
        try:
            import yaml
            self.logger.info(f"Starting cleanup for runner: {runner}")
            workflow_dict = yaml.safe_load(workflow_yaml)

            if not workflow_dict or 'jobs' not in workflow_dict:
                self.logger.warning("No jobs found in workflow, returning original")
                return workflow_yaml

            # Process each job
            total_removed = 0
            for job_name, job_config in workflow_dict['jobs'].items():
                if 'steps' not in job_config:
                    continue

                original_step_count = len(job_config['steps'])

                # Filter out platform-mismatched steps
                cleaned_steps = []
                for step in job_config['steps']:
                    if 'run' not in step:
                        cleaned_steps.append(step)
                        continue

                    run_command = step['run']
                    step_name = step.get('name', 'unnamed')

                    # Convert run_command to string if it's not already
                    if not isinstance(run_command, str):
                        run_command = str(run_command)

                    # Normalize to lowercase for case-insensitive matching
                    run_command_lower = run_command.lower()

                    # For Linux/Mac runners, skip Windows commands
                    if runner in ['ubuntu-latest', 'macos-latest']:
                        windows_patterns = ['mvnw.cmd', 'gradlew.bat', '.bat', '.cmd', 'powershell', '.exe']
                        if any(pattern.lower() in run_command_lower for pattern in windows_patterns):
                            self.logger.info(f"REMOVING Windows step '{step_name}' from Linux workflow: {run_command[:100]}")
                            total_removed += 1
                            continue  # Skip this step

                    # For Windows runners, skip Unix commands
                    elif runner == 'windows-latest':
                        if run_command.startswith('./') and not any(ext in run_command_lower for ext in ['.cmd', '.bat', '.exe']):
                            self.logger.info(f"REMOVING Unix step '{step_name}' from Windows workflow: {run_command[:100]}")
                            total_removed += 1
                            continue  # Skip this step

                    cleaned_steps.append(step)

                self.logger.info(f"Job '{job_name}': {original_step_count} steps -> {len(cleaned_steps)} steps (removed {original_step_count - len(cleaned_steps)})")
                job_config['steps'] = cleaned_steps

            self.logger.info(f"Cleanup complete: Removed {total_removed} platform-mismatched steps total")

            # Convert back to YAML
            return yaml.dump(workflow_dict, default_flow_style=False, sort_keys=False)
        except Exception as e:
            self.logger.error(f"Platform command cleaning failed: {str(e)}, returning original workflow")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return workflow_yaml

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

        # Extract git repository URL if present
        git_match = re.search(r'git\s+(?:branch:\s*["\']([^"\']+)["\'],?\s*)?url:\s*["\']([^"\']+)["\']', jenkinsfile)
        if git_match:
            pipeline_data['git_url'] = git_match.group(2)
            if git_match.group(1):
                pipeline_data['git_branch'] = git_match.group(1)

        # Extract stages using a simpler approach that works with complex nesting
        # Find each stage by name first, then extract everything until the next stage or end
        stage_starts = [(m.start(), m.group(1)) for m in re.finditer(r'stage\s*\(["\']([^"\']+)["\']\)', jenkinsfile)]

        for i, (start_pos, stage_name) in enumerate(stage_starts):
            # Get content from this stage start to next stage start (or end)
            end_pos = stage_starts[i + 1][0] if i + 1 < len(stage_starts) else len(jenkinsfile)
            stage_content = jenkinsfile[start_pos:end_pos]

            steps = []

            # Extract shell commands from anywhere in the stage content
            # Look for sh 'command' or sh "command"
            sh_commands = re.findall(r"sh\s+['\"]([^'\"]+)['\"]", stage_content)
            for cmd in sh_commands:
                steps.append(f"sh '{cmd}'")

            # Look for bat 'command' or bat "command"
            bat_commands = re.findall(r"bat\s+['\"]([^'\"]+)['\"]", stage_content)
            for cmd in bat_commands:
                steps.append(f"bat '{cmd}'")

            # Look for echo commands
            echo_commands = re.findall(r"echo\s+['\"]([^'\"]+)['\"]", stage_content)
            for cmd in echo_commands:
                steps.append(f"echo '{cmd}'")

            # Look for git commands
            if 'git ' in stage_content and 'git ' not in ''.join(steps):
                steps.append('git checkout')

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

        # Detect if this is a Maven project based on steps
        is_maven_project = any(
            'mvnw' in str(step).lower() or 'mvn ' in str(step).lower()
            for stage in pipeline_data['stages']
            for step in stage['steps']
        )

        # Add checkout step - use custom repo URL if specified
        if 'git_url' in pipeline_data and pipeline_data['git_url']:
            repo_url = pipeline_data['git_url'].replace('https://github.com/', '').removesuffix('.git')
            job['steps'].append({
                'name': 'Checkout repository',
                'uses': 'actions/checkout@v4',
                'with': {
                    'repository': repo_url,
                    'ref': pipeline_data.get('git_branch', 'main')
                }
            })
        else:
            job['steps'].append({
                'name': 'Checkout code',
                'uses': 'actions/checkout@v4'
            })

        # Add Java setup for Maven projects
        if is_maven_project:
            job['steps'].append({
                'name': 'Set up JDK 17',
                'uses': 'actions/setup-java@v4',
                'with': {
                    'java-version': '17',
                    'distribution': 'temurin',
                    'cache': 'maven'
                }
            })
            job['steps'].append({
                'name': 'Make Maven wrapper executable',
                'run': 'chmod +x mvnw'
            })

        # Convert each stage to steps
        for stage in pipeline_data['stages']:
            for step in stage['steps']:
                converted_step = self._convert_step(step, stage['name'], pipeline_data)
                if converted_step:
                    job['steps'].append(converted_step)

        # Add artifact upload for Maven projects
        if is_maven_project:
            job['steps'].append({
                'name': 'Upload JAR artifact',
                'uses': 'actions/upload-artifact@v4',
                'with': {
                    'name': 'application-jar',
                    'path': 'target/*.jar'
                }
            })

        return job

    def _create_stage_job(self, stage: Dict, pipeline_data: Dict) -> Dict:
        """Create a GitHub Actions job for a single stage."""
        job = {
            'runs-on': pipeline_data['agent'],
            'steps': []
        }

        # Detect if this is a Maven project based on steps
        is_maven_project = any('mvnw' in str(step).lower() or 'mvn ' in str(step).lower() for step in stage['steps'])

        # Add checkout step - use custom repo URL if specified
        if 'git_url' in pipeline_data and pipeline_data['git_url']:
            # Checkout from specified repository
            repo_url = pipeline_data['git_url'].replace('https://github.com/', '').removesuffix('.git')
            job['steps'].append({
                'name': 'Checkout repository',
                'uses': 'actions/checkout@v4',
                'with': {
                    'repository': repo_url,
                    'ref': pipeline_data.get('git_branch', 'main')
                }
            })
        else:
            # Standard checkout
            job['steps'].append({
                'name': 'Checkout code',
                'uses': 'actions/checkout@v4'
            })

        # Add Java setup for Maven projects
        if is_maven_project:
            job['steps'].append({
                'name': 'Set up JDK 17',
                'uses': 'actions/setup-java@v4',
                'with': {
                    'java-version': '17',
                    'distribution': 'temurin',
                    'cache': 'maven'
                }
            })

            # Make mvnw executable
            job['steps'].append({
                'name': 'Make Maven wrapper executable',
                'run': 'chmod +x mvnw'
            })

        # Convert stage steps
        for step in stage['steps']:
            converted_step = self._convert_step(step, stage['name'], pipeline_data)
            if converted_step:
                job['steps'].append(converted_step)

        # Add artifact upload for package stage with Maven
        if is_maven_project and stage['name'].lower() in ['package', 'build']:
            job['steps'].append({
                'name': 'Upload JAR artifact',
                'uses': 'actions/upload-artifact@v4',
                'with': {
                    'name': 'application-jar',
                    'path': 'target/*.jar'
                }
            })

        return job

    def _convert_step(self, jenkins_step: str, stage_name: str, pipeline_data: Dict) -> Optional[Dict]:
        """Convert a single Jenkins step to GitHub Actions step."""
        step = None

        # Handle sh/bat commands
        if jenkins_step.startswith('sh ') or jenkins_step.startswith('bat '):
            # Extract command
            command = re.search(r'["\']([^"\']+)["\']', jenkins_step)
            if command:
                cmd = command.group(1)
                step = {
                    'name': f'{stage_name}: {cmd[:40]}',
                    'run': cmd
                }

        # Handle echo commands
        elif jenkins_step.startswith('echo '):
            command = re.search(r'echo\s+["\']([^"\']+)["\']', jenkins_step)
            if command:
                step = {
                    'name': command.group(1),
                    'run': f'echo "{command.group(1)}"'
                }

        # Handle checkout - skip it as we already added it at the job level
        elif 'checkout' in jenkins_step.lower() or ('git' in jenkins_step.lower() and 'git_url' in pipeline_data):
            # Skip since we handle checkout at job level
            return None

        # Handle artifact archiving
        elif 'archiveArtifacts' in jenkins_step:
            artifacts_match = re.search(r'artifacts:\s*["\']([^"\']+)["\']', jenkins_step)
            if artifacts_match:
                step = {
                    'name': 'Upload artifacts',
                    'uses': 'actions/upload-artifact@v4',
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

        # Generic command fallback - skip common control structures
        elif jenkins_step and jenkins_step not in ['{', '}', 'if', 'else', 'script']:
            step = {
                'name': f'{stage_name}: {jenkins_step[:40]}',
                'run': jenkins_step.strip().rstrip(';')
            }

        return step

    async def migrate_pipeline(self, jenkinsfile: str, project_name: str, use_llm: bool = True) -> Dict:
        """
        Main migration method with LLM capabilities.

        Uses LangGraph to orchestrate: parse -> generate -> cleanup -> report
        with automatic fallbacks from LLM to regex/template on failure.
        """
        try:
            self.logger.info(f"Starting LangGraph migration pipeline for: {project_name}")

            result = await self.graph.ainvoke({
                "jenkinsfile_content": jenkinsfile,
                "project_name": project_name,
                "use_llm": use_llm,
            })

            if not result.get("success"):
                return {
                    'success': False,
                    'error': result.get('error', 'Migration failed')
                }

            self.logger.info(f"Successfully migrated pipeline: {project_name}")

            return {
                'success': True,
                'github_workflow': result.get('cleaned_yaml', result.get('workflow_yaml', '')),
                'migration_report': result.get('migration_report', {}),
                'warnings': result.get('warnings', [])
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
    jenkins_url: str = "http://localhost:8080"
    jenkins_username: str = "admin"
    jenkins_password: str = "admin"
    job_name: str
    github_token: str
    github_repo_name: Optional[str] = None
    create_repo: bool = True
    private_repo: bool = False


class CreateJobRequest(BaseModel):
    """Request to create a Jenkins job."""
    jenkins_url: str = "http://localhost:8080"
    jenkins_username: str = "admin"
    jenkins_password: str = "admin"
    job_name: str
    config_xml: str



@app.get("/migration/jenkins/test")
@app.get("/dev/migration/jenkins/test")
async def test_jenkins_connection(
    jenkins_url: str = "http://localhost:8080",
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
    jenkins_url: str = "http://localhost:8080",
    username: str = "admin",
    password: str = "admin"
):
    """
    List all Jenkins jobs.

    Query parameters:
    - jenkins_url: Jenkins server URL (default: http://localhost:8080)
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
    jenkins_url: str = "http://localhost:8080",
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

        # Step 3: Get GitHub token (from request or env var)
        github_token = request.github_token
        if not github_token or github_token.strip() == "":
            github_token = os.getenv('GITHUB_TOKEN', '')
            if not github_token:
                raise HTTPException(
                    status_code=500,
                    detail="GitHub token not provided and GITHUB_TOKEN env var not set"
                )
            migration_agent.logger.info("Loaded GitHub token from environment variable")

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
    jenkins_url: str = "http://localhost:8080",
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
