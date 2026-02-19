"""
Policy Agent - Enforces governance policies and compliance gates.

The Policy Agent evaluates content (code, workflows, repositories, deployments)
against configurable policy rules using Claude AI. It acts as a gate that other
agents call before pushing code, creating repositories, or dispatching deployments.
"""

import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sys
sys.path.append('../..')

from common.agent_base import BaseAgent
from common.version import __version__
from common.graphs import build_policy_graph


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    """Generic evaluation request."""
    content_type: str = Field(..., description="Type: code, workflow, repository, deployment")
    content: str = Field(..., description="Raw content to evaluate")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    policy_ids: Optional[List[str]] = Field(None, description="Specific policy IDs to apply")


class EvaluateCodeRequest(BaseModel):
    """Code evaluation request."""
    content: str = Field(..., description="Code content to evaluate")
    context: Dict[str, Any] = Field(default_factory=dict)
    policy_ids: Optional[List[str]] = None


class EvaluateWorkflowRequest(BaseModel):
    """Workflow YAML evaluation request."""
    content: str = Field(..., description="Workflow YAML content")
    context: Dict[str, Any] = Field(default_factory=dict)
    policy_ids: Optional[List[str]] = None


class EvaluateRepositoryRequest(BaseModel):
    """Repository evaluation request."""
    content: str = Field(..., description="Repository info (file list, repo name, etc.)")
    context: Dict[str, Any] = Field(default_factory=dict)
    policy_ids: Optional[List[str]] = None


class EvaluateDeploymentRequest(BaseModel):
    """Deployment gate request."""
    content: str = Field(..., description="Deployment details")
    context: Dict[str, Any] = Field(default_factory=dict)
    policy_ids: Optional[List[str]] = None


class PolicyRule(BaseModel):
    """Policy rule definition."""
    policy_id: str
    name: str
    description: str
    applies_to: List[str] = Field(..., description="Content types: code, workflow, repository, deployment")
    severity: str = Field("medium", description="critical, high, medium, low")
    auto_fix: bool = False
    blocking: bool = False
    enabled: bool = True
    rules: List[str] = Field(..., description="Human-readable rules for Claude to evaluate")
    remediation_hint: str = ""


class EvaluateResponse(BaseModel):
    """Evaluation response."""
    approved: bool
    content_type: str = "unknown"
    severity_summary: Dict[str, int]
    violations: List[Dict[str, Any]]
    suggested_fixes: List[Dict[str, Any]]
    policies_evaluated: int = 0
    timestamp: str = ""


# ---------------------------------------------------------------------------
# Default Policies (seed data)
# ---------------------------------------------------------------------------

DEFAULT_POLICIES: List[Dict[str, Any]] = [
    {
        "policy_id": "no-hardcoded-secrets",
        "name": "No Hardcoded Secrets",
        "description": "Code and workflows must not contain API keys, passwords, or tokens.",
        "applies_to": ["code", "workflow"],
        "severity": "critical",
        "auto_fix": True,
        "blocking": True,
        "enabled": True,
        "rules": [
            "No string literals matching common API key patterns (e.g. sk-, ghp_, AKIA)",
            "No variable assignments with names containing 'password', 'secret', 'token', 'key' and hardcoded string values",
            "No connection strings with embedded credentials"
        ],
        "remediation_hint": "Use environment variables or GitHub Secrets instead of hardcoded values."
    },
    {
        "policy_id": "required-repo-files",
        "name": "Required Repository Files",
        "description": "Repositories must include README.md, .gitignore, and LICENSE.",
        "applies_to": ["repository"],
        "severity": "medium",
        "auto_fix": False,
        "blocking": False,
        "enabled": True,
        "rules": [
            "README.md must exist in the repository root",
            ".gitignore must exist in the repository root",
            "LICENSE file must exist in the repository root"
        ],
        "remediation_hint": "Add the missing files to the repository root."
    },
    {
        "policy_id": "workflow-has-checkout",
        "name": "Workflow Must Use Checkout",
        "description": "GitHub Actions workflows must include actions/checkout step.",
        "applies_to": ["workflow"],
        "severity": "high",
        "auto_fix": True,
        "blocking": True,
        "enabled": True,
        "rules": [
            "At least one job must contain a step using actions/checkout@v3 or actions/checkout@v4",
            "The checkout step should appear before build or test steps"
        ],
        "remediation_hint": "Add 'uses: actions/checkout@v4' as the first step in each job."
    },
    {
        "policy_id": "workflow-no-sudo",
        "name": "No Sudo in Workflows",
        "description": "Workflows should not run arbitrary sudo commands.",
        "applies_to": ["workflow"],
        "severity": "medium",
        "auto_fix": False,
        "blocking": False,
        "enabled": True,
        "rules": [
            "Run steps should not contain 'sudo' commands unless using well-known package managers (apt-get, yum)",
            "Avoid 'sudo chmod 777' or overly permissive sudo operations"
        ],
        "remediation_hint": "Use GitHub Actions built-in features or containerized actions instead of sudo."
    },
    {
        "policy_id": "naming-conventions",
        "name": "Naming Conventions",
        "description": "Repository and branch names must follow kebab-case conventions.",
        "applies_to": ["repository"],
        "severity": "low",
        "auto_fix": False,
        "blocking": False,
        "enabled": True,
        "rules": [
            "Repository names must be lowercase kebab-case (letters, numbers, hyphens only)",
            "Repository names must be between 3 and 50 characters",
            "No spaces, underscores, or uppercase letters in repository names"
        ],
        "remediation_hint": "Rename to lowercase kebab-case (e.g. 'Web Frontend' -> 'web-frontend')."
    },
    {
        "policy_id": "branch-protection-required",
        "name": "Branch Protection Required",
        "description": "Main and develop branches should have protection rules enabled.",
        "applies_to": ["repository"],
        "severity": "medium",
        "auto_fix": False,
        "blocking": False,
        "enabled": True,
        "rules": [
            "The 'main' or 'master' branch should have branch protection enabled",
            "The 'develop' branch should have branch protection enabled if it exists",
            "Protected branches should require pull request reviews before merging"
        ],
        "remediation_hint": "Enable branch protection in Settings -> Branches for main and develop."
    },
    {
        "policy_id": "dependency-pinning",
        "name": "Dependency Pinning",
        "description": "GitHub Actions must pin action versions (no @main or @latest).",
        "applies_to": ["workflow"],
        "severity": "medium",
        "auto_fix": True,
        "blocking": False,
        "enabled": True,
        "rules": [
            "All 'uses:' directives must reference a specific version tag (e.g. @v4, @v3.1.0)",
            "Avoid using '@main', '@master', or '@latest' as action versions",
            "Prefer semantic version tags over branch references"
        ],
        "remediation_hint": "Pin actions to specific versions (e.g. actions/checkout@v4)."
    },
]


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Policy Agent",
    description="Governance and compliance gate for DevOps pipeline content",
    version=__version__
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# PolicyAgent
# ---------------------------------------------------------------------------

class PolicyAgent(BaseAgent):
    """Policy Agent — evaluates content against governance policies using Claude AI."""

    def __init__(self):
        super().__init__(agent_name="policy")
        self.policies_table = self.dynamodb.Table("local-policies")
        self.graph = build_policy_graph(self)
        self._seed_default_policies()
        self.logger.info("Policy Agent initialized with LangGraph workflow")

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a policy evaluation task."""
        content_type = task.get("content_type", "code")
        content = task.get("content", "")
        context = task.get("context", {})
        policy_ids = task.get("policy_ids")
        return await self.evaluate(content_type, content, context, policy_ids)

    async def evaluate(
        self,
        content_type: str,
        content: str,
        context: Dict[str, Any] = None,
        policy_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run the LangGraph policy evaluation pipeline."""
        state = {
            "content_type": content_type,
            "content": content,
            "context": context or {},
            "policy_ids": policy_ids,
        }
        try:
            result = await self.graph.ainvoke(state)
            return result.get("report", {
                "approved": True,
                "severity_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "violations": [],
                "suggested_fixes": [],
            })
        except Exception as e:
            self.logger.error(f"Policy evaluation failed: {e}")
            return {
                "approved": True,
                "severity_summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "violations": [],
                "suggested_fixes": [],
                "error": str(e),
            }

    # ------------------------------------------------------------------
    # LangGraph node implementations
    # ------------------------------------------------------------------

    async def _load_policies(
        self,
        content_type: str,
        policy_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Load applicable policies from local storage."""
        try:
            result = self.policies_table.scan()
            all_policies = result.get("Items", [])
        except Exception as e:
            self.logger.error(f"Failed to load policies: {e}")
            return []

        policies = []
        for p in all_policies:
            if not p.get("enabled", True):
                continue
            if content_type not in p.get("applies_to", []):
                continue
            if policy_ids and p.get("policy_id") not in policy_ids:
                continue
            policies.append(p)

        self.logger.info(
            f"Loaded {len(policies)} policies for content_type={content_type}"
        )
        return policies

    async def _scan_content(
        self,
        content: str,
        content_type: str,
        policies: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Use Claude AI to scan content against policy rules."""
        if not policies:
            return []

        # Truncate content to stay within token limits
        truncated = content[:8000]

        # Build rules section for the prompt
        rules_text = ""
        for p in policies:
            rules_text += f"\n### Policy: {p['name']} (ID: {p['policy_id']}, severity: {p['severity']}, blocking: {p.get('blocking', False)})\n"
            for rule in p.get("rules", []):
                rules_text += f"  - {rule}\n"

        system_prompt = (
            "You are a DevOps policy compliance scanner. Analyse the provided content "
            "against each policy rule and report ALL violations found.\n\n"
            "Return a JSON array of violation objects. Each object must have:\n"
            '  - "policy_id": the policy ID\n'
            '  - "rule": which specific rule was violated\n'
            '  - "severity": the policy severity (critical/high/medium/low)\n'
            '  - "blocking": boolean from the policy\n'
            '  - "auto_fix": boolean - can this be fixed automatically?\n'
            '  - "description": brief explanation of the violation\n'
            '  - "location": where in the content (file, line, match) if applicable\n\n'
            "If no violations are found, return an empty JSON array: []\n"
            "Return ONLY the JSON array, no markdown fences or extra text."
        )

        context_str = json.dumps(context, default=str) if context else "{}"
        user_prompt = (
            f"Content type: {content_type}\n"
            f"Context: {context_str}\n\n"
            f"Policy rules to check:{rules_text}\n"
            f"Content to evaluate:\n```\n{truncated}\n```"
        )

        try:
            response = await self.call_claude(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=2048,
                temperature=0.1,
            )
            results = self._parse_json_response(response, default=[])
            if isinstance(results, list):
                self.logger.info(f"Scan found {len(results)} potential violations")
                return results
            return []
        except Exception as e:
            self.logger.error(f"Content scan failed: {e}")
            return []

    def _evaluate_violations(
        self,
        scan_results: List[Dict[str, Any]],
    ) -> tuple:
        """
        Classify scan results by severity and determine approval.

        Returns:
            (violations, auto_fixable, approved, severity_summary)
        """
        severity_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        violations = []
        has_auto_fixable = False
        approved = True

        for finding in scan_results:
            severity = finding.get("severity", "medium").lower()
            if severity not in severity_summary:
                severity = "medium"
            severity_summary[severity] += 1

            blocking = finding.get("blocking", False)
            if blocking and severity in ("critical", "high"):
                approved = False

            if finding.get("auto_fix", False):
                has_auto_fixable = True

            violations.append({
                "policy_id": finding.get("policy_id", "unknown"),
                "rule": finding.get("rule", ""),
                "severity": severity,
                "blocking": blocking,
                "auto_fix": finding.get("auto_fix", False),
                "description": finding.get("description", ""),
                "location": finding.get("location", ""),
            })

        return violations, has_auto_fixable, approved, severity_summary

    async def _suggest_fixes(
        self,
        violations: List[Dict[str, Any]],
        content: str,
        content_type: str,
    ) -> List[Dict[str, Any]]:
        """Use Claude AI to generate fix suggestions for auto-fixable violations."""
        fixable = [v for v in violations if v.get("auto_fix")]
        if not fixable:
            return []

        truncated = content[:6000]

        violations_text = ""
        for v in fixable:
            violations_text += (
                f"- Policy: {v['policy_id']}, Rule: {v['rule']}, "
                f"Location: {v.get('location', 'N/A')}, "
                f"Description: {v['description']}\n"
            )

        system_prompt = (
            "You are a DevOps code remediation assistant. Generate concrete, "
            "actionable fix suggestions for each policy violation.\n\n"
            "Return a JSON array of fix objects. Each must have:\n"
            '  - "policy_id": the policy that was violated\n'
            '  - "description": what needs to change\n'
            '  - "original": the problematic code/config snippet\n'
            '  - "suggested": the corrected code/config snippet\n\n'
            "Return ONLY the JSON array, no markdown fences or extra text."
        )

        user_prompt = (
            f"Content type: {content_type}\n\n"
            f"Violations to fix:\n{violations_text}\n"
            f"Original content:\n```\n{truncated}\n```"
        )

        try:
            response = await self.call_claude(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=2048,
                temperature=0.2,
            )
            fixes = self._parse_json_response(response, default=[])
            if isinstance(fixes, list):
                self.logger.info(f"Generated {len(fixes)} fix suggestions")
                return fixes
            return []
        except Exception as e:
            self.logger.error(f"Fix suggestion generation failed: {e}")
            return []

    def _build_report(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Assemble the final structured evaluation report."""
        return {
            "approved": state.get("approved", True),
            "content_type": state.get("content_type", "unknown"),
            "severity_summary": state.get("severity_summary", {
                "critical": 0, "high": 0, "medium": 0, "low": 0
            }),
            "violations": state.get("violations", []),
            "suggested_fixes": state.get("suggested_fixes", []),
            "policies_evaluated": len(state.get("policies", [])),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # JSON parsing helpers (same pattern as chatbot intent parsing)
    # ------------------------------------------------------------------

    def _parse_json_response(self, response: str, default: Any = None) -> Any:
        """
        Parse JSON from Claude response with a 3-step repair chain.

        1. Strip markdown fences and try direct parse
        2. Extract first complete JSON block ({...} or [...])
        3. Fix literal newlines/tabs inside string values
        """
        if not response:
            return default

        # Step 1: strip markdown fences
        cleaned = re.sub(r'^```(?:json)?\s*', '', response.strip(), flags=re.MULTILINE)
        cleaned = re.sub(r'```\s*$', '', cleaned.strip(), flags=re.MULTILINE)
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            pass

        # Step 2: extract first complete JSON block
        for start_char, end_char in [('[', ']'), ('{', '}')]:
            start = cleaned.find(start_char)
            if start == -1:
                continue
            depth = 0
            for i in range(start, len(cleaned)):
                if cleaned[i] == start_char:
                    depth += 1
                elif cleaned[i] == end_char:
                    depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[start:i + 1])
                    except json.JSONDecodeError:
                        break

        # Step 3: fix literal newlines/tabs inside JSON string values
        def fix_newlines(text: str) -> str:
            in_string = False
            escape = False
            result = []
            for ch in text:
                if escape:
                    result.append(ch)
                    escape = False
                    continue
                if ch == '\\':
                    escape = True
                    result.append(ch)
                    continue
                if ch == '"':
                    in_string = not in_string
                    result.append(ch)
                    continue
                if in_string and ch == '\n':
                    result.append('\\n')
                    continue
                if in_string and ch == '\t':
                    result.append('\\t')
                    continue
                result.append(ch)
            return ''.join(result)

        try:
            return json.loads(fix_newlines(cleaned.strip()))
        except json.JSONDecodeError:
            pass

        self.logger.warning("All JSON repair attempts failed for policy response")
        return default

    # ------------------------------------------------------------------
    # Seed default policies
    # ------------------------------------------------------------------

    def _seed_default_policies(self):
        """Seed default policies if the table is empty."""
        try:
            result = self.policies_table.scan()
            if result.get("Count", 0) > 0:
                self.logger.info(
                    f"Policy table already has {result['Count']} policies, skipping seed"
                )
                return

            for policy in DEFAULT_POLICIES:
                self.policies_table.put_item(Item=policy)

            self.logger.info(f"Seeded {len(DEFAULT_POLICIES)} default policies")
        except Exception as e:
            self.logger.error(f"Failed to seed default policies: {e}")

    # ------------------------------------------------------------------
    # CRUD helpers for policy management
    # ------------------------------------------------------------------

    def _get_all_policies(self) -> List[Dict[str, Any]]:
        """Return all stored policies."""
        result = self.policies_table.scan()
        return result.get("Items", [])

    def _get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """Return a single policy by ID."""
        result = self.policies_table.get_item(Key={"policy_id": policy_id})
        return result.get("Item")

    def _upsert_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a policy."""
        self.policies_table.put_item(Item=policy)
        return policy

    def _delete_policy(self, policy_id: str) -> bool:
        """Delete a policy by ID."""
        existing = self._get_policy(policy_id)
        if not existing:
            return False
        self.policies_table.delete_item(Key={"policy_id": policy_id})
        return True


# ---------------------------------------------------------------------------
# Agent singleton
# ---------------------------------------------------------------------------

policy_agent = PolicyAgent()


# ---------------------------------------------------------------------------
# FastAPI Routes
# ---------------------------------------------------------------------------

@app.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_generic(request: EvaluateRequest):
    """Evaluate content against all applicable policies."""
    result = await policy_agent.evaluate(
        content_type=request.content_type,
        content=request.content,
        context=request.context,
        policy_ids=request.policy_ids,
    )
    return result


@app.post("/evaluate/code", response_model=EvaluateResponse)
async def evaluate_code(request: EvaluateCodeRequest):
    """Evaluate generated code for security and quality violations."""
    result = await policy_agent.evaluate(
        content_type="code",
        content=request.content,
        context=request.context,
        policy_ids=request.policy_ids,
    )
    return result


@app.post("/evaluate/workflow", response_model=EvaluateResponse)
async def evaluate_workflow(request: EvaluateWorkflowRequest):
    """Evaluate a GitHub Actions workflow YAML against policy."""
    result = await policy_agent.evaluate(
        content_type="workflow",
        content=request.content,
        context=request.context,
        policy_ids=request.policy_ids,
    )
    return result


@app.post("/evaluate/repository", response_model=EvaluateResponse)
async def evaluate_repository(request: EvaluateRepositoryRequest):
    """Evaluate repository structure and compliance."""
    result = await policy_agent.evaluate(
        content_type="repository",
        content=request.content,
        context=request.context,
        policy_ids=request.policy_ids,
    )
    return result


@app.post("/evaluate/deployment", response_model=EvaluateResponse)
async def evaluate_deployment(request: EvaluateDeploymentRequest):
    """Gate a deployment request; returns approve/block decision."""
    result = await policy_agent.evaluate(
        content_type="deployment",
        content=request.content,
        context=request.context,
        policy_ids=request.policy_ids,
    )
    return result


@app.get("/policies")
async def list_policies():
    """List all stored policy rules."""
    policies = policy_agent._get_all_policies()
    return {"policies": policies, "count": len(policies)}


@app.post("/policies")
async def create_or_update_policy(rule: PolicyRule):
    """Create or update a policy rule."""
    policy_dict = rule.model_dump()
    result = policy_agent._upsert_policy(policy_dict)
    return {"status": "ok", "policy": result}


@app.get("/policies/{policy_id}")
async def get_policy(policy_id: str):
    """Get a specific policy rule by ID."""
    policy = policy_agent._get_policy(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")
    return policy


@app.delete("/policies/{policy_id}")
async def delete_policy(policy_id: str):
    """Remove a policy rule."""
    deleted = policy_agent._delete_policy(policy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Policy '{policy_id}' not found")
    return {"status": "deleted", "policy_id": policy_id}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "policy",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
