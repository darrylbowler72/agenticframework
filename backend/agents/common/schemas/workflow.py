"""
Pydantic schemas for workflow and service generation requests.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ServiceScaffoldRequest(BaseModel):
    """Request model for generating a microservice."""

    service_name: str = Field(..., description="Service name in kebab-case")
    language: str = Field(default="python", description="Programming language")
    database: str = Field(default="postgresql", description="Database type")
    api_type: str = Field(default="rest", description="API type (rest, grpc, graphql)")
    environment: str = Field(default="dev", description="Target environment")
    features: Optional[List[str]] = Field(default=None, description="Additional features to include")


class WorkflowRequest(BaseModel):
    """Request model for creating a workflow."""

    template: str = Field(..., description="Workflow template name")
    requested_by: str = Field(..., description="Email of requestor")
    parameters: Dict[str, Any] = Field(..., description="Template parameters")


class WorkflowResponse(BaseModel):
    """Response model for workflow creation."""

    workflow_id: str
    status: str
    template: str
    parameters: Dict[str, Any]
    created_at: datetime
    estimated_completion: Optional[str] = None


class WorkflowStatusResponse(BaseModel):
    """Response model for workflow status."""

    workflow_id: str
    status: str
    progress: int
    current_step: str
    completed_steps: List[str]
    remaining_steps: List[str]
    error: Optional[str] = None


class RemediationRequest(BaseModel):
    """Request model for remediation."""

    issue_type: str = Field(..., description="Type of issue (deployment-failure, security-vulnerability, etc.)")
    service_name: str = Field(..., description="Service name")
    environment: str = Field(..., description="Environment")
    error_details: Optional[Dict[str, Any]] = Field(default=None, description="Error details")
    vulnerability_details: Optional[Dict[str, Any]] = Field(default=None, description="Vulnerability details")


class RemediationResponse(BaseModel):
    """Response model for remediation."""

    remediation_id: str
    issue_type: str
    service_name: str
    status: str
    actions_taken: List[str]
    created_at: datetime


class GenerationResponse(BaseModel):
    """Response model for code generation."""

    service_name: str
    repository_url: str
    artifact_s3_key: str
    files_generated: int
    language: str
    database: str
