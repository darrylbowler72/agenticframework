# Policy Agent

The Policy Agent (port 8005) is a governance and compliance layer that evaluates content at every stage of the DevOps pipeline. Other agents call it before pushing code, creating repositories, generating workflows, or dispatching deployments.

## Technology Approach

The Policy Agent uses **Claude AI with English-language rules** instead of a formal policy engine like Open Policy Agent (OPA) / Rego.

| | Claude AI + English Rules | OPA / Rego |
|---|---|---|
| **Rule authoring** | Natural language — anyone can write rules | Rego DSL — requires learning a new language |
| **Flexibility** | Handles nuance, context, fuzzy matching | Strict logical evaluation only |
| **Consistency** | LLM may vary across runs (mitigated by temperature 0.1) | Deterministic |
| **Dependencies** | Already available (all agents use Claude) | Requires additional infrastructure |
| **Best for** | Local dev tools, small teams, advisory policies | Production enforcement, audit requirements |

This approach is consistent with all other agents in the framework and keeps policy rules accessible to anyone who can describe a rule in plain English.

## LangGraph Policy Graph

The agent workflow is orchestrated as a LangGraph StateGraph:

```
load_policies
     |
scan_content  (Claude analyses content against loaded policy rules)
     |
evaluate_violations  (classify severity, determine approval)
     |
     +-- (violations & auto_fixable) --> suggest_fixes --> build_report --> END
     |
     +-- (violations, not fixable) -------------------> build_report --> END
     |
     +-- (no violations) -----------------------------> build_report --> END
```

| Node | Description |
|------|-------------|
| `load_policies` | Read applicable policies from `/data/db/local-policies.json`, filter by `content_type` and `enabled` |
| `scan_content` | Claude AI call with policy rules in system prompt, temperature 0.1 |
| `evaluate_violations` | Synchronous severity classification, sets `approved` flag |
| `suggest_fixes` | Claude AI call for auto-fixable violations only |
| `build_report` | Assemble structured JSON report |

## API Reference

### Evaluation Endpoints

#### `POST /evaluate`

Generic evaluation — specify `content_type` in the request body.

```json
{
  "content_type": "code",
  "content": "API_KEY = 'sk-abc123'\nimport os\n...",
  "context": {"repo_name": "my-service", "framework": "fastapi"},
  "policy_ids": null
}
```

#### `POST /evaluate/code`

Evaluate generated code for security and quality violations.

```json
{
  "content": "import os\nDB_PASSWORD = 'hunter2'\n...",
  "context": {"repo_name": "my-service"},
  "policy_ids": ["no-hardcoded-secrets"]
}
```

#### `POST /evaluate/workflow`

Evaluate a GitHub Actions workflow YAML.

```json
{
  "content": "name: CI\non: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: npm test",
  "context": {"repo_name": "web-app"}
}
```

#### `POST /evaluate/repository`

Evaluate repository structure and compliance.

```json
{
  "content": "{\"files\": [\"src/index.js\", \"package.json\"], \"repo_name\": \"web-frontend\"}",
  "context": {"repo_name": "web-frontend"}
}
```

#### `POST /evaluate/deployment`

Gate a deployment request.

```json
{
  "content": "{\"branch\": \"release/1.2.0\", \"environment\": \"staging\"}",
  "context": {"repo": "web-frontend"}
}
```

### Response Format

All evaluation endpoints return:

```json
{
  "approved": true,
  "content_type": "code",
  "severity_summary": {
    "critical": 0,
    "high": 0,
    "medium": 1,
    "low": 0
  },
  "violations": [
    {
      "policy_id": "no-hardcoded-secrets",
      "rule": "No variable assignments with names containing 'password'...",
      "severity": "critical",
      "blocking": true,
      "auto_fix": true,
      "description": "Hardcoded password found in DB_PASSWORD assignment",
      "location": "line 2"
    }
  ],
  "suggested_fixes": [
    {
      "policy_id": "no-hardcoded-secrets",
      "description": "Replace hardcoded password with environment variable",
      "original": "DB_PASSWORD = 'hunter2'",
      "suggested": "DB_PASSWORD = os.getenv('DB_PASSWORD')"
    }
  ],
  "policies_evaluated": 2,
  "timestamp": "2025-01-15T10:30:00.000000"
}
```

**Decision logic**: `approved=false` when any **blocking** policy has a **critical** or **high** severity violation.

### Policy CRUD Endpoints

#### `GET /policies`

List all stored policy rules.

```bash
curl http://localhost:8005/policies
```

#### `POST /policies`

Create or update a policy rule.

```bash
curl -X POST http://localhost:8005/policies \
  -H "Content-Type: application/json" \
  -d '{
    "policy_id": "no-eval",
    "name": "No eval() Usage",
    "description": "Code must not use eval() or exec() functions",
    "applies_to": ["code"],
    "severity": "high",
    "auto_fix": false,
    "blocking": true,
    "enabled": true,
    "rules": [
      "No calls to eval() function",
      "No calls to exec() function",
      "No use of compile() with exec mode"
    ],
    "remediation_hint": "Use safer alternatives like json.loads() or ast.literal_eval()."
  }'
```

#### `GET /policies/{policy_id}`

Get a specific policy rule.

```bash
curl http://localhost:8005/policies/no-hardcoded-secrets
```

#### `DELETE /policies/{policy_id}`

Remove a policy rule.

```bash
curl -X DELETE http://localhost:8005/policies/naming-conventions
```

#### `GET /health`

Health check.

```bash
curl http://localhost:8005/health
# {"status": "healthy", "agent": "policy", "version": "1.1.0", "timestamp": "..."}
```

## Policy Storage

Policies are stored in `/data/db/local-policies.json` via the `LocalDynamoDB` table `local-policies`.

### Schema

```json
{
  "policy_id": "no-hardcoded-secrets",
  "name": "No Hardcoded Secrets",
  "description": "Code and workflows must not contain API keys, passwords, or tokens.",
  "applies_to": ["code", "workflow"],
  "severity": "critical",
  "auto_fix": true,
  "blocking": true,
  "enabled": true,
  "rules": [
    "No string literals matching common API key patterns (e.g. sk-, ghp_, AKIA)",
    "No variable assignments with names containing 'password', 'secret', 'token', 'key' and hardcoded string values",
    "No connection strings with embedded credentials"
  ],
  "remediation_hint": "Use environment variables or GitHub Secrets instead of hardcoded values."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `policy_id` | string | Unique identifier |
| `name` | string | Human-readable name |
| `description` | string | What this policy enforces |
| `applies_to` | string[] | Content types: `code`, `workflow`, `repository`, `deployment` |
| `severity` | string | `critical`, `high`, `medium`, `low` |
| `auto_fix` | bool | Whether fix suggestions are generated |
| `blocking` | bool | Whether critical/high violations block approval |
| `enabled` | bool | Whether this policy is active |
| `rules` | string[] | Plain-English rules passed to Claude for evaluation |
| `remediation_hint` | string | Guidance shown to users when violations are found |

## Default Policies

The agent ships with 7 default policies, seeded on first startup (only if the table is empty):

| Policy ID | Applies To | Severity | Blocking | Description |
|-----------|-----------|----------|----------|-------------|
| `no-hardcoded-secrets` | code, workflow | critical | yes | No API keys, passwords, tokens in content |
| `required-repo-files` | repository | medium | no | README.md, .gitignore, LICENSE must exist |
| `workflow-has-checkout` | workflow | high | yes | Workflow must use `actions/checkout` |
| `workflow-no-sudo` | workflow | medium | no | Workflows should not run arbitrary `sudo` commands |
| `naming-conventions` | repository | low | no | Repo names must be kebab-case, no spaces |
| `branch-protection-required` | repository | medium | no | main/develop should have branch protection |
| `dependency-pinning` | workflow | medium | no | Action versions must be pinned (no `@main` or `@latest`) |

Default policies are preserved across restarts. User modifications (adds, deletes, updates) are not overwritten.

## GitHub Actions Integration Model

The Policy Agent operates as an **internal pre-push gate**, not an external GitHub App or webhook.

```
Agent (e.g. CodeGen)
  |
  +-- generates code
  |
  +-- POST /evaluate/code  -->  Policy Agent  -->  approved: true/false
  |
  +-- if approved: push to GitHub
  +-- if blocked: return error to caller
```

This means:
- Policies are enforced **before** content reaches GitHub
- No GitHub App installation or webhook configuration required
- Works entirely within the local container network
- Other agents call the Policy Agent via HTTP before their push/deploy steps

## Integration Points

| Caller Agent | When | Endpoint | Policies Applied |
|-------------|------|----------|-----------------|
| `codegen-agent` | Before `push_to_repo` | `/evaluate/code` | no-hardcoded-secrets |
| `chatbot-agent` | After `setup_project` | `/evaluate/repository` | required-repo-files, naming-conventions, branch-protection-required |
| `chatbot-agent` | After workflow generation | `/evaluate/workflow` | workflow-has-checkout, dependency-pinning |
| `migration-agent` | Before returning workflow | `/evaluate/workflow` | workflow-has-checkout, workflow-no-sudo, dependency-pinning |
| `planner-agent` | Before dispatching deploy | `/evaluate/deployment` | All deployment policies |
| `remediation-agent` | After auto-fix | `/evaluate/code` | no-hardcoded-secrets |

## Use Cases

### UC-1: Prevent Hardcoded Secrets in Generated Code

**Trigger**: CodeGen Agent finishes generating code, before pushing to GitHub.

The CodeGen agent sends the generated files to `POST /evaluate/code`. Claude scans for API key patterns, password variables, and connection strings. If found, the Policy Agent returns `approved=false` with violation details and fix suggestions (e.g. replace `API_KEY = 'sk-abc123'` with `API_KEY = os.getenv('API_KEY')`). CodeGen skips the push and returns an error to the caller.

### UC-2: Enforce Required Repository Files

**Trigger**: Chatbot Agent completes `setup_project`.

The chatbot sends the list of files pushed to GitHub to `POST /evaluate/repository`. The Policy Agent checks for `README.md`, `.gitignore`, and `LICENSE`. Missing files are returned as medium-severity warnings. The chatbot appends a compliance notice to its response.

### UC-3: Validate Workflow Security

**Trigger**: Migration Agent generates a GitHub Actions workflow.

The migration agent sends the YAML to `POST /evaluate/workflow`. Policies check for `actions/checkout`, `sudo` usage, and pinned action versions. Missing checkout is blocking (high severity); sudo and unpinned versions are warnings.

### UC-4: Deployment Gate

**Trigger**: Planner Agent is about to dispatch a deploy task.

The planner sends deployment details to `POST /evaluate/deployment`. The Policy Agent checks branch validity, CI status, and security advisories. If blocked, the planner returns a `{"status": "blocked", "reason": "...", "violations": [...]}` response.

### UC-5: Branch Protection Enforcement

**Trigger**: Chatbot creates gitflow branches on a new repo.

After creating branches, the chatbot calls `POST /evaluate/repository`. The Policy Agent checks whether main/develop have branch protection enabled and returns warnings with instructions if not.

### UC-6: Naming Convention Compliance

**Trigger**: Any repo creation via Chatbot.

Before creating, the chatbot calls `POST /evaluate/repository` with the proposed name. The Policy Agent checks kebab-case, length, and character rules. Non-compliant names get a `suggested_name` in the response.

### UC-7: Dependency Vulnerability Scanning

**Trigger**: CodeGen or `setup_project` creates dependency files.

The calling agent passes `requirements.txt` or `package.json` contents to `POST /evaluate/code`. Claude analyses declared versions for known insecure patterns and returns warnings with suggested upgrades.

## Calling from Other Agents

```python
import httpx
import os

async def check_policy(content_type: str, content: str, context: dict) -> dict:
    policy_url = os.getenv("POLICY_URL", "http://policy-agent:8005")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{policy_url}/evaluate/{content_type}",
            json={"content": content, "context": context}
        )
        return resp.json()
    # Returns: {"approved": bool, "severity_summary": {...}, "violations": [...], ...}
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `POLICY_URL` | `http://policy-agent:8005` | Service discovery URL |
| `LOCAL_MODE` | `true` | Always true in local-podman branch |
| `ENVIRONMENT` | `local` | Environment prefix for storage tables |
| `ANTHROPIC_API_KEY` | (required) | Claude AI API key |

## Building and Running

```bash
# Build the image
podman.exe build --build-arg VERSION=1.1.0 -f backend/Dockerfile.policy -t policy-agent .

# Run the container
podman.exe run -d --name policy-agent \
  --network agentic-local \
  -v local-data:/data \
  -p 8005:8005 \
  --env-file .env \
  -e LOCAL_MODE=true \
  -e ENVIRONMENT=local \
  -e MCP_GITHUB_URL=http://mcp-github:8100 \
  policy-agent

# Verify
curl http://localhost:8005/health
curl http://localhost:8005/policies
```
