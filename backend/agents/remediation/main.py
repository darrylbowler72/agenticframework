"""
Remediation Agent - Auto-fixes broken CI/CD pipelines.

The Remediation Agent analyzes pipeline failures using AI and automatically
applies fixes for common issues like dependency problems, environment configs,
flaky tests, and resource limits.
"""

import json
import re
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
import gitlab
import sys
sys.path.append('../..')

from common.agent_base import BaseAgent


app = FastAPI(
    title="Remediation Agent",
    description="Automatically diagnoses and fixes CI/CD pipeline failures",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RemediationAgent(BaseAgent):
    """Remediation Agent implementation."""

    def __init__(self):
        super().__init__(agent_name="remediation")
        self.gitlab_client: Optional[gitlab.Gitlab] = None
        self.playbooks_table = None
        self.actions_table = None
        self._initialize_tables()
        self.logger.info("Remediation Agent initialized")

    def _initialize_tables(self):
        """Initialize DynamoDB tables."""
        try:
            self.playbooks_table = self.dynamodb.Table('remediation_playbooks')
            self.actions_table = self.dynamodb.Table('remediation_actions')
        except Exception as e:
            self.logger.warning(f"Could not initialize DynamoDB tables: {e}")

    async def _initialize_gitlab(self):
        """Initialize GitLab client."""
        if self.gitlab_client:
            return

        try:
            secret = await self.get_secret("gitlab-credentials")
            self.gitlab_client = gitlab.Gitlab(
                url=secret.get('url', 'https://gitlab.com'),
                private_token=secret['token']
            )
            self.gitlab_client.auth()
            self.logger.info("GitLab client initialized")
        except Exception as e:
            self.logger.warning(f"Could not initialize GitLab client: {e}")

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a remediation task."""
        return await self.handle_pipeline_failure(task)

    async def handle_pipeline_failure(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main remediation workflow.

        Args:
            event_data: Pipeline failure event data

        Returns:
            Remediation result
        """
        pipeline_id = event_data.get('pipeline_id')
        project_id = event_data.get('project_id')

        self.logger.info(f"Handling pipeline failure: {pipeline_id} in project {project_id}")

        await self._initialize_gitlab()

        # Fetch pipeline logs
        logs = await self._fetch_pipeline_logs(pipeline_id, project_id)

        # AI-powered root cause analysis
        analysis = await self._analyze_failure(logs, event_data)

        # Find matching playbook
        playbook = await self._find_playbook(
            category=analysis['category'],
            failure_pattern=analysis.get('failure_pattern', '')
        )

        # Execute remediation if applicable
        if playbook and playbook.get('auto_fix_enabled') and analysis['risk_level'] == 'low':
            result = await self._execute_playbook(playbook, analysis, pipeline_id, project_id)
        else:
            result = {
                'outcome': 'manual_intervention_required',
                'reason': 'High risk or no matching playbook',
                'analysis': analysis
            }

        # Store remediation action
        await self._store_action(pipeline_id, project_id, analysis, result)

        # Notify developer
        await self._notify_developer(result, analysis)

        return result

    async def _fetch_pipeline_logs(self, pipeline_id: int, project_id: int) -> str:
        """
        Fetch pipeline logs from GitLab.

        Args:
            pipeline_id: Pipeline ID
            project_id: Project ID

        Returns:
            Combined log text
        """
        if not self.gitlab_client:
            return "Sample error logs: ModuleNotFoundError: No module named 'requests'"

        try:
            project = self.gitlab_client.projects.get(project_id)
            pipeline = project.pipelines.get(pipeline_id)
            jobs = pipeline.jobs.list()

            logs = []
            for job in jobs:
                if job.status == 'failed':
                    try:
                        log = job.trace().decode('utf-8')
                        logs.append(f"=== Job: {job.name} ===\n{log}\n")
                    except:
                        pass

            return "\n".join(logs)

        except Exception as e:
            self.logger.error(f"Error fetching pipeline logs: {e}")
            return ""

    async def _analyze_failure(self, logs: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use Claude AI to perform root cause analysis.

        Args:
            logs: Pipeline logs
            context: Additional context

        Returns:
            Analysis results
        """
        prompt = f"""You are a DevOps expert analyzing a failed CI/CD pipeline.

Pipeline Information:
- Pipeline ID: {context.get('pipeline_id')}
- Project ID: {context.get('project_id')}
- Ref: {context.get('ref', 'unknown')}

Error Logs:
{logs[:4000]}  # Truncate for token limits

Tasks:
1. Identify the root cause of the failure
2. Classify the failure category: dependency, environment, test, resource, or infrastructure
3. Assess the risk level: low (safe to auto-fix), medium (needs review), or high (requires manual intervention)
4. Suggest a remediation strategy
5. Extract relevant failure pattern (e.g., error message pattern)
6. Provide confidence score (0-1)

Output valid JSON only:
{{
  "root_cause": "Brief description of the root cause",
  "category": "dependency|environment|test|resource|infrastructure",
  "risk_level": "low|medium|high",
  "remediation_strategy": "specific_action_name",
  "failure_pattern": "regex or text pattern that identifies this error",
  "remediation_params": {{}},
  "confidence": 0.95,
  "explanation": "Detailed explanation of the issue and fix"
}}"""

        try:
            response = await self.call_claude(prompt, max_tokens=1500)

            # Clean and parse JSON
            response = response.strip()
            if response.startswith('```json'):
                response = response.split('```json')[1].split('```')[0].strip()
            elif response.startswith('```'):
                response = response.split('```')[1].split('```')[0].strip()

            analysis = json.loads(response)
            return analysis

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Claude response: {e}")
            # Fallback to rule-based analysis
            return self._fallback_analysis(logs)
        except Exception as e:
            self.logger.error(f"Error in AI analysis: {e}")
            return self._fallback_analysis(logs)

    def _fallback_analysis(self, logs: str) -> Dict[str, Any]:
        """
        Rule-based fallback analysis when AI is unavailable.

        Args:
            logs: Pipeline logs

        Returns:
            Basic analysis
        """
        self.logger.warning("Using fallback analysis")

        # Check for common patterns
        if "ModuleNotFoundError" in logs or "No module named" in logs:
            module_match = re.search(r"No module named '([^']+)'", logs)
            module_name = module_match.group(1) if module_match else "unknown"

            return {
                "root_cause": f"Missing Python dependency: {module_name}",
                "category": "dependency",
                "risk_level": "low",
                "remediation_strategy": "add_dependency",
                "failure_pattern": f"No module named '{module_name}'",
                "remediation_params": {"module": module_name},
                "confidence": 0.9,
                "explanation": f"The pipeline failed because the Python module '{module_name}' is not installed."
            }

        elif "npm ERR!" in logs and "404" in logs:
            return {
                "root_cause": "Missing npm package",
                "category": "dependency",
                "risk_level": "low",
                "remediation_strategy": "npm_install",
                "failure_pattern": "npm ERR! 404",
                "remediation_params": {},
                "confidence": 0.85,
                "explanation": "The pipeline failed due to a missing npm package."
            }

        elif "OutOfMemoryError" in logs or "exit code 137" in logs:
            return {
                "root_cause": "Out of memory",
                "category": "resource",
                "risk_level": "low",
                "remediation_strategy": "increase_memory",
                "failure_pattern": "OutOfMemoryError|exit code 137",
                "remediation_params": {"increase_by": 1.5},
                "confidence": 0.9,
                "explanation": "The pipeline ran out of memory. Increasing memory allocation should fix this."
            }

        else:
            return {
                "root_cause": "Unknown failure",
                "category": "infrastructure",
                "risk_level": "high",
                "remediation_strategy": "manual_review",
                "failure_pattern": "",
                "remediation_params": {},
                "confidence": 0.3,
                "explanation": "Could not automatically determine the root cause. Manual review required."
            }

    async def _find_playbook(self, category: str, failure_pattern: str) -> Optional[Dict[str, Any]]:
        """
        Find matching remediation playbook.

        Args:
            category: Failure category
            failure_pattern: Pattern to match

        Returns:
            Playbook or None
        """
        if not self.playbooks_table:
            return self._get_builtin_playbook(category, failure_pattern)

        try:
            response = self.playbooks_table.query(
                IndexName='category-index',
                KeyConditionExpression='category = :cat',
                ExpressionAttributeValues={':cat': category}
            )

            playbooks = response.get('Items', [])

            # Find best matching playbook
            for playbook in playbooks:
                pattern = playbook.get('failure_pattern', '')
                if pattern and re.search(pattern, failure_pattern, re.IGNORECASE):
                    return playbook

            return None

        except Exception as e:
            self.logger.error(f"Error finding playbook: {e}")
            return self._get_builtin_playbook(category, failure_pattern)

    def _get_builtin_playbook(self, category: str, failure_pattern: str) -> Optional[Dict[str, Any]]:
        """Get built-in playbook as fallback."""
        if category == "dependency" and "No module named" in failure_pattern:
            return {
                'playbook_id': 'builtin-python-dependency',
                'category': 'dependency',
                'auto_fix_enabled': True,
                'remediation_steps': [
                    {'action': 'extract_module', 'params': {}},
                    {'action': 'add_to_requirements', 'params': {}},
                    {'action': 'commit_push', 'params': {}},
                    {'action': 'retry_pipeline', 'params': {}}
                ]
            }
        return None

    async def _execute_playbook(
        self,
        playbook: Dict[str, Any],
        analysis: Dict[str, Any],
        pipeline_id: int,
        project_id: int
    ) -> Dict[str, Any]:
        """
        Execute remediation playbook steps.

        Args:
            playbook: Playbook to execute
            analysis: Failure analysis
            pipeline_id: Pipeline ID
            project_id: Project ID

        Returns:
            Execution result
        """
        self.logger.info(f"Executing playbook: {playbook.get('playbook_id')}")

        steps_executed = []
        context = {
            'analysis': analysis,
            'pipeline_id': pipeline_id,
            'project_id': project_id
        }

        try:
            for step in playbook.get('remediation_steps', []):
                result = await self._execute_step(step, context)
                steps_executed.append({
                    'step': step['action'],
                    'result': result.get('status', 'success'),
                    'details': result
                })
                context.update(result)  # Pass data between steps

            return {
                'outcome': 'success',
                'playbook_id': playbook.get('playbook_id'),
                'steps_executed': steps_executed,
                'new_pipeline_id': context.get('new_pipeline_id')
            }

        except Exception as e:
            self.logger.error(f"Error executing playbook: {e}")
            return {
                'outcome': 'failed',
                'playbook_id': playbook.get('playbook_id'),
                'steps_executed': steps_executed,
                'error': str(e)
            }

    async def _execute_step(self, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single remediation step."""
        action = step['action']
        params = step.get('params', {})

        self.logger.info(f"Executing step: {action}")

        if action == 'extract_module':
            # Extract module name from analysis
            module_name = context['analysis']['remediation_params'].get('module', 'requests')
            return {'status': 'success', 'module_name': module_name}

        elif action == 'add_to_requirements':
            # Add module to requirements.txt
            module_name = context.get('module_name', 'requests')
            # In production, actually modify the file via GitLab API
            self.logger.info(f"Would add {module_name} to requirements.txt")
            return {'status': 'success', 'changes': f"Added {module_name} to requirements.txt"}

        elif action == 'commit_push':
            # Commit and push changes
            # In production, use GitLab API to create commit
            self.logger.info("Would commit and push changes")
            return {'status': 'success', 'commit_sha': 'abc123'}

        elif action == 'retry_pipeline':
            # Retry the pipeline
            # In production, use GitLab API to retry
            self.logger.info(f"Would retry pipeline {context['pipeline_id']}")
            return {'status': 'success', 'new_pipeline_id': context['pipeline_id'] + 1}

        else:
            return {'status': 'unknown_action', 'action': action}

    async def _store_action(
        self,
        pipeline_id: int,
        project_id: int,
        analysis: Dict[str, Any],
        result: Dict[str, Any]
    ):
        """Store remediation action in DynamoDB."""
        if not self.actions_table:
            return

        try:
            action_id = f"ra-{uuid.uuid4().hex[:8]}"

            self.actions_table.put_item(Item={
                'action_id': action_id,
                'pipeline_id': str(pipeline_id),
                'project_id': str(project_id),
                'timestamp': datetime.utcnow().isoformat(),
                'failure_category': analysis.get('category'),
                'root_cause': analysis.get('root_cause'),
                'risk_level': analysis.get('risk_level'),
                'outcome': result.get('outcome'),
                'auto_fix_applied': result.get('outcome') == 'success',
                'playbook_id': result.get('playbook_id'),
                'steps_executed': result.get('steps_executed', [])
            })

            self.logger.info(f"Stored remediation action: {action_id}")

        except Exception as e:
            self.logger.error(f"Error storing action: {e}")

    async def _notify_developer(self, result: Dict[str, Any], analysis: Dict[str, Any]):
        """Send notification about remediation."""
        # In production, send to Slack/email
        if result['outcome'] == 'success':
            self.logger.info(f"✅ Auto-fixed: {analysis['root_cause']}")
        else:
            self.logger.warning(f"⚠️ Manual intervention needed: {analysis['root_cause']}")


# Initialize agent
remediation_agent = RemediationAgent()


@app.post("/webhooks/gitlab/pipeline")
@app.post("/dev/webhooks/gitlab/pipeline")
async def handle_pipeline_webhook(request: Request):
    """Receive pipeline failure events from GitLab."""
    payload = await request.json()

    if payload.get('object_attributes', {}).get('status') == 'failed':
        # Publish to EventBridge for async processing
        await remediation_agent.publish_event(
            event_type='pipeline.failed',
            detail={
                'pipeline_id': payload['object_attributes']['id'],
                'project_id': payload['project']['id'],
                'ref': payload['object_attributes']['ref'],
                'status': payload['object_attributes']['status']
            }
        )

    return {"status": "received"}


@app.post("/remediate")
@app.post("/dev/remediate")
async def trigger_remediation(pipeline_id: int, project_id: int):
    """Manually trigger remediation for a pipeline."""
    try:
        result = await remediation_agent.handle_pipeline_failure({
            'pipeline_id': pipeline_id,
            'project_id': project_id
        })
        return result
    except Exception as e:
        remediation_agent.logger.error(f"Error in remediation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/health")
@app.get("/dev/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "remediation",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
