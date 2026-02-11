"""
LangGraph graph builders for all agents.

Provides factory functions that build compiled LangGraph StateGraph instances.
Each graph encodes the workflow logic, conditional routing, and retry cycles
for a specific agent.
"""

from langgraph.graph import StateGraph, END

from common.graph_states import (
    WorkflowState,
    MigrationState,
    ChatState,
    RemediationState,
    CodeGenState,
)


# ---------------------------------------------------------------------------
# Planner Agent Graph
# ---------------------------------------------------------------------------

def build_planner_graph(agent):
    """
    Build LangGraph for the Planner Agent.

    Graph: plan_tasks -> store_workflow -> dispatch_tasks -> END
                |
                (on failure) -> fallback_plan -> store_workflow -> ...

    Args:
        agent: PlannerAgent instance (provides node implementations)

    Returns:
        Compiled LangGraph
    """

    async def plan_tasks(state: WorkflowState) -> dict:
        """Use Claude to decompose request into tasks."""
        try:
            tasks = await agent._plan_tasks(
                template=state["template"],
                parameters=state["parameters"],
            )
            return {"tasks": tasks, "status": "planned"}
        except Exception as e:
            agent.logger.error(f"AI planning failed: {e}")
            return {"tasks": [], "status": "plan_failed", "error": str(e)}

    async def fallback_plan(state: WorkflowState) -> dict:
        """Generate fallback plan when AI planning fails."""
        tasks = agent._fallback_plan(state["template"], state["parameters"])
        return {"tasks": tasks, "status": "planned_fallback"}

    async def store_workflow(state: WorkflowState) -> dict:
        """Persist workflow and tasks to DynamoDB."""
        await agent._store_workflow(
            workflow_id=state["workflow_id"],
            request_data={
                "template": state["template"],
                "parameters": state["parameters"],
                "requested_by": state.get("requested_by", "unknown"),
            },
            tasks=state["tasks"],
        )
        return {"status": "stored"}

    async def dispatch_tasks(state: WorkflowState) -> dict:
        """Publish task.created events to EventBridge."""
        for task in state["tasks"]:
            await agent.publish_event(
                detail_type="task.created",
                detail={
                    "workflow_id": state["workflow_id"],
                    "task_id": task["task_id"],
                    "agent": task["agent"],
                    "input_params": task["input_params"],
                },
            )
        return {"status": "in_progress"}

    def needs_fallback(state: WorkflowState) -> str:
        if state.get("status") == "plan_failed" or not state.get("tasks"):
            return "fallback_plan"
        return "store_workflow"

    graph = StateGraph(WorkflowState)
    graph.add_node("plan_tasks", plan_tasks)
    graph.add_node("fallback_plan", fallback_plan)
    graph.add_node("store_workflow", store_workflow)
    graph.add_node("dispatch_tasks", dispatch_tasks)

    graph.set_entry_point("plan_tasks")
    graph.add_conditional_edges("plan_tasks", needs_fallback, {
        "fallback_plan": "fallback_plan",
        "store_workflow": "store_workflow",
    })
    graph.add_edge("fallback_plan", "store_workflow")
    graph.add_edge("store_workflow", "dispatch_tasks")
    graph.add_edge("dispatch_tasks", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Migration Agent Graph
# ---------------------------------------------------------------------------

def build_migration_graph(agent):
    """
    Build LangGraph for the Migration Agent.

    Graph:
        parse_llm --(success)--> generate_llm --(success)--> cleanup -> report -> END
            |                        |
        (failure)                (failure)
            v                        v
        parse_regex              generate_template -> cleanup -> report -> END

    Args:
        agent: MigrationAgent instance

    Returns:
        Compiled LangGraph
    """

    async def parse_with_llm(state: MigrationState) -> dict:
        """Parse Jenkinsfile using Claude LLM."""
        try:
            pipeline_data = await agent.parse_jenkinsfile_with_llm(
                state["jenkinsfile_content"]
            )
            return {
                "pipeline_data": pipeline_data,
                "parse_method": "llm",
                "runner": pipeline_data.get("agent", "ubuntu-latest"),
            }
        except Exception as e:
            agent.logger.error(f"LLM parsing failed: {e}")
            return {"pipeline_data": {}, "parse_method": "llm_failed"}

    async def parse_with_regex(state: MigrationState) -> dict:
        """Fallback regex-based Jenkinsfile parser."""
        pipeline_data = agent.parse_jenkinsfile(state["jenkinsfile_content"])
        return {
            "pipeline_data": pipeline_data,
            "parse_method": "regex",
            "runner": pipeline_data.get("agent", "ubuntu-latest"),
        }

    async def generate_with_llm(state: MigrationState) -> dict:
        """Generate GitHub Actions YAML with Claude."""
        try:
            yaml_str = await agent.generate_workflow_with_llm(
                state["pipeline_data"], state["project_name"]
            )
            return {"workflow_yaml": yaml_str, "generation_method": "llm"}
        except Exception as e:
            agent.logger.error(f"LLM generation failed: {e}")
            return {"workflow_yaml": "", "generation_method": "llm_failed"}

    async def generate_with_template(state: MigrationState) -> dict:
        """Fallback template-based workflow generation."""
        import yaml as yaml_lib

        workflow_dict = agent.convert_to_github_actions(
            state["pipeline_data"], state["project_name"]
        )
        yaml_str = yaml_lib.dump(workflow_dict, default_flow_style=False, sort_keys=False)
        return {"workflow_yaml": yaml_str, "generation_method": "template"}

    async def cleanup_platform(state: MigrationState) -> dict:
        """Remove platform-incompatible commands."""
        runner = state.get("runner", "ubuntu-latest")
        cleaned = agent._clean_platform_commands(state["workflow_yaml"], runner)
        return {"cleaned_yaml": cleaned}

    async def build_report(state: MigrationState) -> dict:
        """Build migration report and collect warnings."""
        from datetime import datetime

        pipeline_data = state["pipeline_data"]
        warnings = []

        if not pipeline_data.get("triggers"):
            warnings.append("No triggers found in Jenkinsfile. Default push trigger added.")
        if pipeline_data.get("type") == "scripted":
            warnings.append("Scripted pipeline detected. Manual review recommended for complex logic.")

        report = {
            "source_type": "Jenkins",
            "target_type": "GitHub Actions",
            "pipeline_type": pipeline_data.get("type", "unknown"),
            "stages_converted": len(pipeline_data.get("stages", [])),
            "environment_variables": len(pipeline_data.get("environment", {})),
            "triggers_converted": len(pipeline_data.get("triggers", [])),
            "parse_method": state.get("parse_method", "unknown"),
            "generation_method": state.get("generation_method", "unknown"),
            "timestamp": datetime.utcnow().isoformat(),
        }

        return {
            "migration_report": report,
            "warnings": warnings,
            "success": True,
        }

    def route_after_parse(state: MigrationState) -> str:
        if state.get("parse_method") == "llm_failed" or not state.get("pipeline_data"):
            return "parse_with_regex"
        if state["pipeline_data"].get("type") == "unknown":
            return "parse_with_regex"
        return "generate_with_llm"

    def route_after_generate(state: MigrationState) -> str:
        if state.get("generation_method") == "llm_failed" or not state.get("workflow_yaml"):
            return "generate_with_template"
        return "cleanup_platform"

    graph = StateGraph(MigrationState)
    graph.add_node("parse_with_llm", parse_with_llm)
    graph.add_node("parse_with_regex", parse_with_regex)
    graph.add_node("generate_with_llm", generate_with_llm)
    graph.add_node("generate_with_template", generate_with_template)
    graph.add_node("cleanup_platform", cleanup_platform)
    graph.add_node("build_report", build_report)

    graph.set_entry_point("parse_with_llm")
    graph.add_conditional_edges("parse_with_llm", route_after_parse, {
        "parse_with_regex": "parse_with_regex",
        "generate_with_llm": "generate_with_llm",
    })
    graph.add_edge("parse_with_regex", "generate_with_llm")
    graph.add_conditional_edges("generate_with_llm", route_after_generate, {
        "generate_with_template": "generate_with_template",
        "cleanup_platform": "cleanup_platform",
    })
    graph.add_edge("generate_with_template", "cleanup_platform")
    graph.add_edge("cleanup_platform", "build_report")
    graph.add_edge("build_report", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Chatbot Agent Graph
# ---------------------------------------------------------------------------

def build_chatbot_graph(agent):
    """
    Build LangGraph for the Chatbot Agent.

    Graph:
        analyze_intent --(action_needed)--> execute_action -> compose_response -> END
                       |
                   (no action)
                       v
                   compose_response -> END

    Args:
        agent: ChatbotAgent instance

    Returns:
        Compiled LangGraph
    """

    async def analyze_intent(state: ChatState) -> dict:
        """Use Claude to classify user intent."""
        analysis = await agent.analyze_intent(
            state["user_message"], state["conversation_history"]
        )
        return {
            "intent": analysis.get("intent", "general"),
            "action_needed": analysis.get("action_needed", False),
            "intent_parameters": analysis.get("parameters", {}),
            "intent_response": analysis.get(
                "response",
                "I'm here to help with your DevOps tasks!",
            ),
        }

    async def execute_action(state: ChatState) -> dict:
        """Dispatch action to the appropriate backend agent."""
        result = await agent.execute_action(
            state["intent"], state.get("intent_parameters", {})
        )
        return {"action_result": result}

    async def compose_response(state: ChatState) -> dict:
        """Build final user-facing response including action results."""
        response = state.get("intent_response", "")
        action_result = state.get("action_result")

        if action_result:
            response = agent._format_action_response(
                response, state["intent"], action_result
            )

        return {"final_response": response}

    def needs_action(state: ChatState) -> str:
        if state.get("action_needed"):
            return "execute_action"
        return "compose_response"

    graph = StateGraph(ChatState)
    graph.add_node("analyze_intent", analyze_intent)
    graph.add_node("execute_action", execute_action)
    graph.add_node("compose_response", compose_response)

    graph.set_entry_point("analyze_intent")
    graph.add_conditional_edges("analyze_intent", needs_action, {
        "execute_action": "execute_action",
        "compose_response": "compose_response",
    })
    graph.add_edge("execute_action", "compose_response")
    graph.add_edge("compose_response", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Remediation Agent Graph
# ---------------------------------------------------------------------------

def build_remediation_graph(agent):
    """
    Build LangGraph for the Remediation Agent.

    Graph:
        fetch_logs -> analyze_failure -> find_playbook
                                             |
                           (auto-fixable) ---+--- (manual) -> notify -> END
                                |
                           execute_playbook -> verify -> notify -> END
                                 |                |
                             (fail & retry<3) ----+
                                 |
                             (fail & retry>=3) -> notify -> END

    Args:
        agent: RemediationAgent instance

    Returns:
        Compiled LangGraph
    """

    async def fetch_logs(state: RemediationState) -> dict:
        """Fetch pipeline failure logs."""
        logs = await agent._fetch_pipeline_logs(
            state["pipeline_id"], state["project_id"]
        )
        return {"logs": logs}

    async def analyze_failure(state: RemediationState) -> dict:
        """AI-powered root cause analysis."""
        analysis = await agent._analyze_failure(
            state["logs"], state.get("event_data", {})
        )
        return {"analysis": analysis}

    async def find_playbook(state: RemediationState) -> dict:
        """Find matching remediation playbook."""
        analysis = state["analysis"]
        playbook = await agent._find_playbook(
            category=analysis["category"],
            failure_pattern=analysis.get("failure_pattern", ""),
        )
        return {"playbook": playbook}

    async def execute_playbook(state: RemediationState) -> dict:
        """Execute the auto-fix playbook."""
        result = await agent._execute_playbook(
            state["playbook"],
            state["analysis"],
            state["pipeline_id"],
            state["project_id"],
        )
        retry_count = state.get("retry_count", 0)
        return {"execution_result": result, "retry_count": retry_count + 1}

    async def store_and_notify(state: RemediationState) -> dict:
        """Store action record and notify developer."""
        analysis = state.get("analysis", {})
        result = state.get("execution_result", {"outcome": "manual_intervention_required"})

        await agent._store_action(
            state["pipeline_id"], state["project_id"], analysis, result
        )
        await agent._notify_developer(result, analysis)

        return {
            "outcome": result.get("outcome", "manual_intervention_required"),
            "notification_sent": True,
        }

    def route_after_playbook(state: RemediationState) -> str:
        playbook = state.get("playbook")
        analysis = state.get("analysis", {})

        if (
            playbook
            and playbook.get("auto_fix_enabled")
            and analysis.get("risk_level") == "low"
        ):
            return "execute_playbook"
        return "store_and_notify"

    def route_after_execute(state: RemediationState) -> str:
        result = state.get("execution_result", {})
        retry_count = state.get("retry_count", 0)

        if result.get("outcome") == "success":
            return "store_and_notify"
        if retry_count < 3:
            return "execute_playbook"
        return "store_and_notify"

    graph = StateGraph(RemediationState)
    graph.add_node("fetch_logs", fetch_logs)
    graph.add_node("analyze_failure", analyze_failure)
    graph.add_node("find_playbook", find_playbook)
    graph.add_node("execute_playbook", execute_playbook)
    graph.add_node("store_and_notify", store_and_notify)

    graph.set_entry_point("fetch_logs")
    graph.add_edge("fetch_logs", "analyze_failure")
    graph.add_edge("analyze_failure", "find_playbook")
    graph.add_conditional_edges("find_playbook", route_after_playbook, {
        "execute_playbook": "execute_playbook",
        "store_and_notify": "store_and_notify",
    })
    graph.add_conditional_edges("execute_playbook", route_after_execute, {
        "store_and_notify": "store_and_notify",
        "execute_playbook": "execute_playbook",
    })
    graph.add_edge("store_and_notify", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# CodeGen Agent Graph
# ---------------------------------------------------------------------------

def build_codegen_graph(agent):
    """
    Build LangGraph for the CodeGen Agent.

    Graph:
        generate_templates -> enhance_with_ai -> store_artifacts -> push_to_repo -> generate_readme -> END

    Args:
        agent: CodeGenAgent instance

    Returns:
        Compiled LangGraph
    """

    async def init_github(state: CodeGenState) -> dict:
        """Initialize GitHub MCP client."""
        await agent._initialize_github()
        return {}

    async def generate_templates(state: CodeGenState) -> dict:
        """Generate files from Jinja2 templates."""
        files = await agent._generate_from_templates(
            service_name=state["service_name"],
            language=state["language"],
            database=state["database"],
            api_type=state["api_type"],
        )
        return {"files": files}

    async def enhance_with_ai(state: CodeGenState) -> dict:
        """Use Claude to enhance generated code."""
        files = await agent._enhance_with_ai(
            state["files"], state["service_name"], state["language"]
        )
        return {"files": files}

    async def store_artifacts(state: CodeGenState) -> dict:
        """Store generated files in S3."""
        from datetime import datetime

        artifact_key = f"codegen/{state['service_name']}/{datetime.utcnow().isoformat()}"
        await agent._store_artifacts(artifact_key, state["files"])
        return {"artifact_key": artifact_key}

    async def push_to_repo(state: CodeGenState) -> dict:
        """Create GitHub repo and push code."""
        repo_url = await agent._create_and_push_repository(
            state["service_name"], state["files"]
        )
        return {"repo_url": repo_url}

    async def generate_readme(state: CodeGenState) -> dict:
        """Generate README.md with Claude."""
        readme = await agent._generate_readme(
            state["service_name"],
            state["language"],
            state["database"],
            state["api_type"],
        )
        files = dict(state["files"])
        files["README.md"] = readme
        return {
            "files": files,
            "readme": readme,
            "files_generated": len(files),
            "status": "completed",
        }

    graph = StateGraph(CodeGenState)
    graph.add_node("init_github", init_github)
    graph.add_node("generate_templates", generate_templates)
    graph.add_node("enhance_with_ai", enhance_with_ai)
    graph.add_node("store_artifacts", store_artifacts)
    graph.add_node("push_to_repo", push_to_repo)
    graph.add_node("generate_readme", generate_readme)

    graph.set_entry_point("init_github")
    graph.add_edge("init_github", "generate_templates")
    graph.add_edge("generate_templates", "enhance_with_ai")
    graph.add_edge("enhance_with_ai", "store_artifacts")
    graph.add_edge("store_artifacts", "push_to_repo")
    graph.add_edge("push_to_repo", "generate_readme")
    graph.add_edge("generate_readme", END)

    return graph.compile()
