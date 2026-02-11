"""
LangGraph state definitions for all agent graphs.

Defines TypedDict states used by LangGraph StateGraph instances across agents.
Each state captures the data flowing through the graph nodes.
"""

from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict


class WorkflowState(TypedDict, total=False):
    """State for Planner Agent workflow orchestration graph."""
    # Input
    template: str
    parameters: Dict[str, Any]
    requested_by: str

    # Planning
    workflow_id: str
    tasks: List[Dict[str, Any]]

    # Execution tracking
    completed_tasks: List[str]
    failed_tasks: List[str]
    current_task: Optional[str]

    # Results
    status: str
    error: Optional[str]


class MigrationState(TypedDict, total=False):
    """State for Migration Agent pipeline conversion graph."""
    # Input
    jenkinsfile_content: str
    project_name: str
    use_llm: bool

    # Parsing
    pipeline_data: Dict[str, Any]
    parse_method: str

    # Generation
    workflow_yaml: str
    generation_method: str

    # Validation & cleanup
    cleaned_yaml: str
    runner: str

    # Output
    migration_report: Dict[str, Any]
    warnings: List[str]
    success: bool
    error: Optional[str]


class ChatState(TypedDict, total=False):
    """State for Chatbot Agent intent routing graph."""
    # Input
    session_id: str
    user_message: str
    conversation_history: List[Dict[str, Any]]

    # Intent analysis
    intent: str
    action_needed: bool
    intent_parameters: Dict[str, Any]
    intent_response: str

    # Action execution
    action_result: Optional[Dict[str, Any]]

    # Output
    final_response: str
    messages: List[Dict[str, Any]]


class RemediationState(TypedDict, total=False):
    """State for Remediation Agent feedback loop graph."""
    # Input
    pipeline_id: Any
    project_id: str
    event_data: Dict[str, Any]

    # Analysis
    logs: str
    analysis: Dict[str, Any]

    # Playbook
    playbook: Optional[Dict[str, Any]]

    # Execution
    execution_result: Dict[str, Any]
    retry_count: int

    # Output
    outcome: str
    notification_sent: bool


class CodeGenState(TypedDict, total=False):
    """State for CodeGen Agent code generation graph."""
    # Input
    service_name: str
    language: str
    database: str
    api_type: str
    environment: str

    # Generation
    files: Dict[str, str]
    readme: str

    # Storage & publish
    artifact_key: str
    repo_url: str

    # Output
    files_generated: int
    status: str
    error: Optional[str]
