"""Workflow and task schemas."""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TaskStatusEnum(str, Enum):
    """Task status values."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentType(str, Enum):
    """Agent types."""
    PLANNER = "planner"
    CODEGEN = "codegen"
    DEPLOYMENT = "deployment"
    POLICY = "policy"
    REMEDIATION = "remediation"
    OBSERVABILITY = "observability"


class WorkflowRequest(BaseModel):
    """Request to create a new workflow."""
    template: str = Field(..., description="Template identifier (e.g., 'microservice-rest-api')")
    parameters: Dict[str, Any] = Field(..., description="Template parameters")
    requested_by: str = Field(..., description="User email or identifier")
    priority: int = Field(default=5, ge=1, le=10, description="Priority 1-10")


class TaskCreate(BaseModel):
    """Task definition."""
    task_id: str
    agent: AgentType
    description: str
    input_params: Dict[str, Any]
    dependencies: List[str] = Field(default_factory=list)
    priority: int = Field(default=5)


class TaskStatus(BaseModel):
    """Task status information."""
    task_id: str
    agent: AgentType
    status: TaskStatusEnum
    description: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    estimated_duration: Optional[str] = None


class WorkflowResponse(BaseModel):
    """Response from workflow creation."""
    workflow_id: str
    status: TaskStatusEnum
    tasks: List[TaskStatus]
    created_at: datetime
    estimated_completion: Optional[str] = None


class WorkflowStatus(BaseModel):
    """Complete workflow status."""
    workflow_id: str
    status: TaskStatusEnum
    requested_by: str
    template: str
    parameters: Dict[str, Any]
    tasks: List[TaskStatus]
    created_at: datetime
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None  # seconds


class ServiceScaffoldRequest(BaseModel):
    """Request to scaffold a new microservice."""
    service_name: str = Field(..., pattern=r'^[a-z][a-z0-9-]*$', description="Service name (kebab-case)")
    language: str = Field(..., description="Programming language (python, nodejs, go)")
    database: str = Field(default="postgresql", description="Database type")
    api_type: str = Field(default="rest", description="API type (rest, grpc, graphql)")
    environment: str = Field(default="dev", description="Target environment")
    advanced_options: Optional[Dict[str, Any]] = Field(default=None, description="Advanced configuration")


class DeploymentRequest(BaseModel):
    """Request to deploy a service."""
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Version to deploy")
    environment: str = Field(..., description="Target environment")
    strategy: str = Field(default="rolling", description="Deployment strategy")
    requested_by: str = Field(..., description="User identifier")


class PolicyValidationRequest(BaseModel):
    """Request to validate policies."""
    type: str = Field(..., description="Type (terraform_plan, dockerfile, k8s_manifest)")
    content: str = Field(..., description="Content to validate (base64 encoded if binary)")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
