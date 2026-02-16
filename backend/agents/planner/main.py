"""
Planner Agent - Orchestrates multi-step workflows.

The Planner Agent receives high-level requests and decomposes them into
actionable tasks for specialized agents.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import sys
sys.path.append('../..')

from common.agent_base import BaseAgent
from common.version import __version__
from common.graphs import build_planner_graph
from common.schemas.workflow import (
    WorkflowRequest,
    WorkflowResponse,
    WorkflowStatus,
    TaskCreate,
    TaskStatus,
    TaskStatusEnum,
    AgentType
)


app = FastAPI(
    title="Planner Agent",
    description="Orchestrates multi-step workflows by decomposing requests into tasks",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PlannerAgent(BaseAgent):
    """Planner Agent implementation."""

    def __init__(self):
        super().__init__(agent_name="planner")
        self.graph = build_planner_graph(self)
        self.logger.info("Planner Agent initialized with LangGraph workflow")

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a planning task."""
        # This is called by EventBridge triggers
        return await self.create_workflow(task)

    async def create_workflow(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new workflow by decomposing the request into tasks.

        Uses LangGraph to orchestrate: plan_tasks -> store_workflow -> dispatch_tasks

        Args:
            request_data: Workflow request data

        Returns:
            Workflow creation result
        """
        workflow_id = f"wf-{uuid.uuid4().hex[:12]}"
        self.logger.info(f"Creating workflow {workflow_id} for template: {request_data.get('template')}")

        result = await self.graph.ainvoke({
            "template": request_data["template"],
            "parameters": request_data["parameters"],
            "requested_by": request_data.get("requested_by", "unknown"),
            "workflow_id": workflow_id,
        })

        tasks = result.get("tasks", [])
        self.logger.info(f"Workflow {workflow_id} created with {len(tasks)} tasks")

        return {
            'workflow_id': workflow_id,
            'status': result.get('status', 'in_progress'),
            'tasks': tasks
        }

    async def _plan_tasks(
        self,
        template: str,
        parameters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Use Claude AI to plan the task breakdown.

        Args:
            template: Template identifier
            parameters: Template parameters

        Returns:
            List of task definitions
        """
        prompt = f"""You are a DevOps workflow planner. Given a request to create infrastructure using a specific template,
break it down into a sequence of tasks for specialized agents.

Template: {template}
Parameters: {json.dumps(parameters, indent=2)}

Available Agents:
- codegen: Generates code, infrastructure templates, CI/CD configs
- policy: Validates security policies and compliance
- deployment: Handles infrastructure provisioning and application deployment
- observability: Sets up monitoring and validates health

Create an execution plan as a JSON array with this structure:
[
  {{
    "task_id": "unique-id",
    "agent": "agent-name",
    "description": "What this task does",
    "input_params": {{}},
    "dependencies": ["task-id-that-must-complete-first"],
    "priority": 1-10
  }}
]

Rules:
1. Tasks must be ordered by dependencies
2. codegen tasks typically come first
3. policy validation should happen before deployment
4. observability checks come last

Output only valid JSON, no additional text."""

        try:
            response = await self.call_claude(prompt, max_tokens=2000)

            # Parse JSON from response
            response = response.strip()
            if response.startswith('```json'):
                response = response.split('```json')[1].split('```')[0].strip()
            elif response.startswith('```'):
                response = response.split('```')[1].split('```')[0].strip()

            tasks = json.loads(response)

            # Add workflow metadata
            for task in tasks:
                task['created_at'] = datetime.utcnow().isoformat()
                task['status'] = 'pending'

            return tasks

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Claude response as JSON: {e}")
            # Fallback to hardcoded plan for common templates
            return self._fallback_plan(template, parameters)
        except Exception as e:
            self.logger.error(f"Error planning tasks: {e}")
            return self._fallback_plan(template, parameters)

    def _fallback_plan(self, template: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fallback task planning when AI is unavailable.

        Args:
            template: Template identifier
            parameters: Template parameters

        Returns:
            Basic task list
        """
        self.logger.warning("Using fallback task planning")

        if template == "microservice-rest-api":
            return [
                {
                    "task_id": f"t-{uuid.uuid4().hex[:8]}",
                    "agent": "codegen",
                    "description": f"Generate {parameters.get('service_name')} microservice code",
                    "input_params": parameters,
                    "dependencies": [],
                    "priority": 1,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "pending"
                },
                {
                    "task_id": f"t-{uuid.uuid4().hex[:8]}",
                    "agent": "policy",
                    "description": "Validate security policies",
                    "input_params": {"service_name": parameters.get('service_name')},
                    "dependencies": [],
                    "priority": 2,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "pending"
                },
                {
                    "task_id": f"t-{uuid.uuid4().hex[:8]}",
                    "agent": "deployment",
                    "description": f"Deploy to {parameters.get('environment', 'dev')}",
                    "input_params": parameters,
                    "dependencies": [],
                    "priority": 3,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "pending"
                }
            ]
        else:
            # Generic single-task plan
            return [
                {
                    "task_id": f"t-{uuid.uuid4().hex[:8]}",
                    "agent": "codegen",
                    "description": f"Execute template {template}",
                    "input_params": parameters,
                    "dependencies": [],
                    "priority": 1,
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "pending"
                }
            ]

    async def _store_workflow(
        self,
        workflow_id: str,
        request_data: Dict[str, Any],
        tasks: List[Dict[str, Any]]
    ):
        """Store workflow and tasks in DynamoDB."""
        if not self.workflows_table:
            self.logger.warning("Workflows table not available, skipping storage")
            return

        try:
            # Store workflow metadata
            self.workflows_table.put_item(Item={
                'workflow_id': workflow_id,
                'task_id': 'METADATA',
                'status': 'in_progress',
                'template': request_data['template'],
                'parameters': request_data['parameters'],
                'requested_by': request_data.get('requested_by', 'unknown'),
                'created_at': datetime.utcnow().isoformat(),
                'task_count': len(tasks)
            })

            # Store individual tasks
            for task in tasks:
                self.workflows_table.put_item(Item={
                    'workflow_id': workflow_id,
                    'task_id': task['task_id'],
                    'agent': task['agent'],
                    'description': task['description'],
                    'status': task['status'],
                    'input_params': task['input_params'],
                    'dependencies': task.get('dependencies', []),
                    'priority': task.get('priority', 5),
                    'created_at': task['created_at']
                })

        except Exception as e:
            self.logger.error(f"Error storing workflow: {e}")

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Retrieve workflow status from DynamoDB.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Workflow status data
        """
        if not self.workflows_table:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Workflow storage not available"
            )

        try:
            # Query all items for this workflow
            response = self.workflows_table.query(
                KeyConditionExpression='workflow_id = :wf_id',
                ExpressionAttributeValues={':wf_id': workflow_id}
            )

            items = response.get('Items', [])
            if not items:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workflow {workflow_id} not found"
                )

            # Separate metadata from tasks
            metadata = next((item for item in items if item['task_id'] == 'METADATA'), None)
            tasks = [item for item in items if item['task_id'] != 'METADATA']

            if not metadata:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Workflow {workflow_id} metadata not found"
                )

            # Determine overall status
            task_statuses = [task['status'] for task in tasks]
            if all(s == 'completed' for s in task_statuses):
                overall_status = 'completed'
            elif any(s == 'failed' for s in task_statuses):
                overall_status = 'failed'
            elif any(s == 'in_progress' for s in task_statuses):
                overall_status = 'in_progress'
            else:
                overall_status = 'pending'

            return {
                'workflow_id': workflow_id,
                'status': overall_status,
                'template': metadata.get('template'),
                'parameters': metadata.get('parameters'),
                'requested_by': metadata.get('requested_by'),
                'created_at': metadata.get('created_at'),
                'tasks': tasks
            }

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(f"Error retrieving workflow status: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )


# Initialize agent
planner_agent = PlannerAgent()


@app.post("/workflows", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
@app.post("/dev/workflows", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(request: WorkflowRequest):
    """
    Create a new workflow.

    The Planner Agent will decompose the request into tasks and
    publish events to EventBridge for execution by specialized agents.
    """
    try:
        result = await planner_agent.create_workflow(request.dict())

        return WorkflowResponse(
            workflow_id=result['workflow_id'],
            status=TaskStatusEnum.IN_PROGRESS,
            template=request.template,
            parameters=request.parameters,
            tasks=[
                TaskStatus(
                    task_id=task['task_id'],
                    agent=AgentType(task['agent']),
                    status=TaskStatusEnum.PENDING,
                    description=task['description'],
                    created_at=datetime.fromisoformat(task['created_at']),
                    estimated_duration="2-5 minutes"
                )
                for task in result['tasks']
            ],
            created_at=datetime.utcnow()
        )

    except Exception as e:
        planner_agent.logger.error(f"Error creating workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/workflows/{workflow_id}", response_model=WorkflowStatus)
@app.get("/dev/workflows/{workflow_id}", response_model=WorkflowStatus)
async def get_workflow(workflow_id: str):
    """Get workflow status."""
    return await planner_agent.get_workflow_status(workflow_id)


@app.get("/health")
@app.get("/dev/health")
@app.get("/planner/health")
@app.get("/dev/planner/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "planner",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
