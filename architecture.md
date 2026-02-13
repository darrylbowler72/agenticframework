# DevOps Agentic Framework - Architecture Documentation

## Table of Contents
1. [Current Deployment Status](#current-deployment-status)
2. [System Overview](#system-overview)
3. [Architecture Principles](#architecture-principles)
4. [Agent Architecture](#agent-architecture)
5. [AWS Infrastructure](#aws-infrastructure)
6. [Data Flow & Orchestration](#data-flow--orchestration)
7. [Integration Architecture](#integration-architecture)
8. [Security & Governance](#security--governance)
9. [Observability & Monitoring](#observability--monitoring)
10. [Developer Experience](#developer-experience)
11. [Deployment Strategy](#deployment-strategy)
12. [API Specifications](#api-specifications)
13. [Scaling & Performance](#scaling--performance)

---

## Current Deployment Status

### Deployed Components (Phase 1)

**Infrastructure Status**: ✅ **FULLY DEPLOYED AND OPERATIONAL**

**Public Access**: https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/

#### ECS Fargate Services (Running)
- **Planner Agent** - `dev-planner-agent` service
  - Container: `773550624765.dkr.ecr.us-east-1.amazonaws.com/planner-agent:latest`
  - Port: 8000
  - Resources: 512 CPU / 1024 MB Memory
  - Health Check: HTTP `/health` endpoint
  - Status: ✅ Active (1/1 running)

- **CodeGen Agent** - `dev-codegen-agent` service
  - Container: `773550624765.dkr.ecr.us-east-1.amazonaws.com/codegen-agent:latest`
  - Port: 8001
  - Resources: 512 CPU / 1024 MB Memory
  - Health Check: HTTP `/health` endpoint
  - Status: ✅ Active (1/1 running)

- **Remediation Agent** - `dev-remediation-agent` service
  - Container: `773550624765.dkr.ecr.us-east-1.amazonaws.com/remediation-agent:latest`
  - Port: 8002
  - Resources: 512 CPU / 1024 MB Memory
  - Health Check: HTTP `/health` endpoint
  - Status: ✅ Active (1/1 running)

- **Chatbot Agent** - `dev-chatbot-agent` service
  - Container: `773550624765.dkr.ecr.us-east-1.amazonaws.com/chatbot-agent:latest`
  - Port: 8003
  - Resources: 512 CPU / 1024 MB Memory
  - Health Check: HTTP `/health` endpoint
  - Status: ✅ Active (1/1 running)
  - **Public Interface**: Accessible via API Gateway at root path (`/`)

- **Migration Agent** - `dev-migration-agent` service
  - Container: `773550624765.dkr.ecr.us-east-1.amazonaws.com/migration-agent:latest`
  - Port: 8004
  - Resources: 512 CPU / 1024 MB Memory
  - Health Check: HTTP `/health` endpoint
  - Status: ✅ Active (1/1 running)
  - **Version**: 1.0.26
  - **Purpose**: Jenkins to GitHub Actions pipeline migration

#### AWS Infrastructure (Deployed)
- **VPC**: Custom VPC with public/private subnets across 2 AZs
- **API Gateway**: HTTP API for agent orchestration (publicly accessible)
  - Base URL: `https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev`
  - Routes: POST /workflows, POST /generate, POST /remediate, POST /chat, POST /migration/*, GET /*, GET /static/*
- **Application Load Balancer**: Internal ALB routing to ECS services
  - 5 target groups (planner, codegen, remediation, chatbot, migration)
  - Health checks configured for all services
- **VPC Link**: Connects API Gateway (public) to ALB (private VPC)
- **EventBridge**: Custom event bus for agent communication
- **DynamoDB**: 4 tables (workflows, deployments, policy-violations, chatbot-sessions)
- **S3**: 4 buckets (artifacts, templates, policy-bundles, terraform-state)
- **Secrets Manager**: 3 secrets (Anthropic API key, GitLab credentials, Slack credentials)
- **CloudWatch**: Log groups for agents and API Gateway
- **ECS Cluster**: Fargate cluster `dev-agentic-cluster` with 5 services
- **ECR**: 5 container repositories for agent images
- **IAM**: Task execution and task roles with appropriate permissions
- **Security Groups**: ECS tasks, ALB, and VPC Link security groups

#### Total Resources Deployed
- **70+ AWS Resources** managed by Terraform
- **Infrastructure State**: Stored in S3 with DynamoDB locking
- **Environment**: Development (`dev`)
- **Region**: us-east-1

### Planned Components (Future Phases)

#### Phase 2: GitOps & CI/CD
- [ ] EKS Cluster for application workloads
- [ ] ArgoCD deployment for GitOps workflows
- [ ] GitLab integration for CI/CD pipelines
- [ ] Deployment Agent implementation

#### Phase 3: Policy & Governance
- [ ] Policy Agent with OPA integration
- [ ] Kyverno admission controls
- [ ] Security scanning (Trivy, tfsec)
- [ ] Compliance reporting

#### Phase 4: Observability
- [ ] Observability Agent implementation
- [ ] OpenTelemetry Collector deployment
- [ ] Grafana dashboards
- [ ] SageMaker anomaly detection

#### Phase 5: Developer Experience
- [ ] Backstage developer portal
- [ ] Software templates
- [ ] Self-service workflows
- [ ] Integration with Slack/Teams

### Current Architecture Diagram

```
                         Internet
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│           AWS API Gateway (HTTP API) - Public                │
│   https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com    │
│   - POST /workflows  - POST /generate   - POST /remediate   │
│   - POST /chat       - POST /migration  - GET /*            │
└────────────────────────┬─────────────────────────────────────┘
                         │ VPC Link
                         ▼
┌──────────────────────────────────────────────────────────────┐
│        Application Load Balancer (Internal/Private)          │
│        - 5 Target Groups with health checks                  │
└────┬─────────┬─────────┬─────────┬─────────┬────────────────┘
     │         │         │         │         │
     ▼         ▼         ▼         ▼         ▼
┌────────┐┌────────┐┌────────┐┌────────┐┌─────────┐
│Planner ││CodeGen ││Remediat││Chatbot ││Migration│
│Agent   ││Agent   ││Agent   ││Agent   ││Agent    │
│(ECS)   ││(ECS)   ││(ECS)   ││(ECS)   ││(ECS)    │
│:8000   ││:8001   ││:8002   ││:8003   ││:8004    │
└────┬───┘└────┬───┘└────┬───┘└────┬───┘└────┬────┘
     │         │         │         │         │
     └─────────┼─────────┼─────────┼─────────┘
               │         │         │
   ┌───────────┼─────────┼─────────┼───────────────┐
   │           │         │         │               │
   ▼           ▼         ▼         ▼               ▼
┌─────────┐┌─────────┐┌────────┐┌─────────┐┌──────────┐
│DynamoDB ││   S3    ││EventBus││Secrets  ││Jenkins   │
│4 Tables ││4 Buckets││        ││Manager  ││API       │
└─────────┘└─────────┘└────────┘└─────────┘└──────────┘
```

### Deployment Commands

The infrastructure was deployed using these scripts:
```bash
# 1. Setup Terraform backend
bash scripts/02-setup-aws-backend.sh

# 2. Deploy infrastructure
bash scripts/03-deploy-infrastructure.sh

# 3. Store secrets
aws secretsmanager put-secret-value \
  --secret-id dev-anthropic-api-key \
  --secret-string "your-api-key"

# 4. Build and deploy containers
bash scripts/05-deploy-agents-podman.sh
```

### Verification Commands

```bash
# Check ECS services
aws ecs list-services --cluster dev-agentic-cluster --region us-east-1

# Check API Gateway endpoint
cd iac/terraform && terraform output api_gateway_url

# Check CloudWatch logs
aws logs tail /aws/ecs/dev-agentic-cluster --follow
```

---

## System Overview

### Purpose
The DevOps Agentic Framework is an autonomous, AI-driven platform designed to accelerate software delivery through intelligent automation. It combines multi-agent systems, GitOps workflows, policy enforcement, and enhanced developer experience to create a comprehensive DevOps automation solution.

### Core Philosophy
- **Autonomous Operations**: AI agents handle complex workflows with minimal human intervention
- **Declarative Configuration**: GitOps-based deployments ensure consistency and version control
- **Policy-First**: Automated governance and compliance checks at every stage
- **Observable by Default**: Comprehensive telemetry and intelligent anomaly detection

### High-Level Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    Developer Interface                       │
│                  (Backstage Portal)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   API Gateway (AWS)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Agent Orchestration Layer                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Planner  │ │ CodeGen  │ │Deployment│ │  Policy  │      │
│  │  Agent   │ │  Agent   │ │  Agent   │ │  Agent   │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│  ┌──────────┐ ┌──────────┐                                 │
│  │Remediate │ │Observ.   │                                 │
│  │  Agent   │ │  Agent   │                                 │
│  └──────────┘ └──────────┘                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         ▼               ▼               ▼
    ┌─────────┐    ┌─────────┐    ┌─────────┐
    │ GitLab  │    │ ArgoCD  │    │  OTel   │
    │   CI    │    │ GitOps  │    │Collector│
    └─────────┘    └─────────┘    └─────────┘
         │               │               │
         └───────────────┼───────────────┘
                         ▼
                  ┌─────────────┐
                  │  EKS/ECS    │
                  │  Workloads  │
                  └─────────────┘
```

---

## Architecture Principles

### 1. Agent-Oriented Design
Each agent is a specialized microservice with a specific domain of expertise. Agents communicate via event-driven messaging and maintain their own state.

### 2. Event-Driven Communication
AWS EventBridge serves as the central nervous system, routing events between agents and external systems.

### 3. Declarative Infrastructure
All infrastructure and application configurations are defined as code and stored in Git repositories.

### 4. Zero-Trust Security
Every interaction requires authentication and authorization. Secrets are managed centrally via AWS Secrets Manager.

### 5. Observable Everything
All agents emit OpenTelemetry-compliant metrics, logs, and traces.

---

## Agent Architecture

### Agent Runtime Model
Each agent follows a consistent runtime pattern:

```
┌──────────────────────────────────────────┐
│              Agent Container             │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │    Event Listener (EventBridge)   │ │
│  └────────┬───────────────────────────┘ │
│           │                              │
│           ▼                              │
│  ┌────────────────────────────────────┐ │
│  │      Agent Logic (AI Model)        │ │
│  │   - Planning / Execution           │ │
│  │   - Context Management             │ │
│  │   - Tool Integration               │ │
│  └────────┬───────────────────────────┘ │
│           │                              │
│           ▼                              │
│  ┌────────────────────────────────────┐ │
│  │    Action Executor / API Client    │ │
│  └────────┬───────────────────────────┘ │
│           │                              │
│           ▼                              │
│  ┌────────────────────────────────────┐ │
│  │   Telemetry Publisher (OTel)      │ │
│  └────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

### Agent Catalog

#### 1. Planner Agent
**Purpose**: Orchestrates multi-step workflows by decomposing high-level requests into actionable tasks.

**Responsibilities**:
- Parse developer requests from Backstage
- Create execution plans with task dependencies
- Assign tasks to appropriate specialized agents
- Monitor overall workflow progress
- Handle exceptions and retries

**Technology Stack**:
- Runtime: AWS Lambda (on-demand) or ECS Fargate (long-running)
- AI Model: Claude API for planning and reasoning
- Storage: DynamoDB for workflow state
- Events: Publishes to EventBridge topic `planner.tasks.created`

**Example Flow**:
```
Input: "Create a new microservice called user-service with REST API, PostgreSQL, and deploy to staging"

Output:
1. Task: Generate repository structure → CodeGen Agent
2. Task: Create Terraform modules for RDS → CodeGen Agent
3. Task: Generate CI/CD pipeline config → CodeGen Agent
4. Task: Deploy infrastructure → Deployment Agent
5. Task: Run compliance checks → Policy Agent
6. Task: Verify health metrics → Observability Agent
```

#### 2. CodeGen Agent (Scaffolding Agent)
**Purpose**: Generates code, infrastructure, and configuration files based on templates and best practices.

**Responsibilities**:
- Generate microservice boilerplate code
- Create Terraform/CloudFormation IaC templates
- Generate CI/CD pipeline configurations (GitLab CI, GitHub Actions)
- Create Kubernetes manifests and Helm charts
- Generate API documentation and README files

**Technology Stack**:
- Runtime: AWS Lambda
- AI Model: Claude API with extended context for code generation
- Template Engine: Jinja2/Mustache for customization
- Storage: S3 for generated artifacts
- Version Control: Pushes to GitLab repositories

**Supported Templates**:
- Microservice patterns: REST API, gRPC, Event-Driven
- Languages: Python (FastAPI), Node.js (Express), Go (Gin)
- Databases: PostgreSQL, DynamoDB, Redis
- Message Queues: SQS, SNS, EventBridge

#### 3. Deployment Agent
**Purpose**: Manages application deployments through GitOps and infrastructure provisioning.

**Responsibilities**:
- Coordinate with ArgoCD for Kubernetes deployments
- Trigger Terraform applies for infrastructure changes
- Manage deployment rollouts and rollbacks
- Handle blue-green and canary deployments
- Validate deployment success criteria

**Technology Stack**:
- Runtime: ECS Fargate (persistent service)
- ArgoCD API integration
- Terraform Cloud/Enterprise API
- AWS EKS API for cluster management
- Storage: DynamoDB for deployment history

**Deployment Strategies**:
- **Rolling Update**: Gradual pod replacement (default)
- **Blue-Green**: Full environment swap
- **Canary**: Progressive traffic shifting (10% → 50% → 100%)

#### 4. Policy Agent
**Purpose**: Enforces organizational policies, security standards, and compliance requirements.

**Responsibilities**:
- Run OPA (Open Policy Agent) policy evaluations
- Execute Kyverno admission controls
- Validate Terraform plans against security baselines
- Check for secrets in code repositories
- Enforce resource tagging and naming conventions
- Generate compliance reports

**Technology Stack**:
- Runtime: AWS Lambda (event-triggered)
- Policy Engines: OPA, Kyverno
- Security Scanning: Trivy, tfsec, Checkov
- Storage: S3 for policy bundles and reports
- Notifications: SNS for policy violations

**Policy Categories**:
1. **Security Policies**: No public S3 buckets, encryption at rest, IAM best practices
2. **Cost Policies**: Resource limits, instance type restrictions
3. **Compliance Policies**: PCI-DSS, HIPAA, SOC2 requirements
4. **Operational Policies**: Required labels, backup configurations

#### 5. Remediation Agent
**Purpose**: Automatically fixes common issues detected by policy or observability agents.

**Responsibilities**:
- Auto-remediate security vulnerabilities (e.g., patch dependencies)
- Fix infrastructure drift detected in Terraform state
- Restart unhealthy pods/services
- Scale resources during load spikes
- Apply automated hotfixes for known issues

**Technology Stack**:
- Runtime: ECS Fargate (persistent service)
- Remediation Playbooks: Stored in S3 as executable scripts
- Approval Workflow: SNS + Lambda for critical changes
- Audit: All actions logged to CloudWatch

**Remediation Types**:
- **Automated**: Low-risk fixes applied immediately
- **Assisted**: Requires human approval via Backstage UI
- **Advisory**: Recommendations without auto-execution

#### 6. Chatbot Agent (✅ Deployed)
**Purpose**: Provides a conversational interface for interacting with all DevOps automation capabilities through natural language.

**Responsibilities**:
- Interpret natural language requests from users
- Route commands to appropriate specialized agents
- Maintain conversation context and session state
- Provide friendly, helpful responses with action summaries
- Support multi-turn conversations for complex workflows

**Technology Stack**:
- Runtime: ECS Fargate (persistent service)
- AI Model: Claude API for intent analysis and conversational responses
- Storage: DynamoDB for chat session management
- Web Interface: FastAPI with HTML/CSS/JS frontend
- Integration: HTTP client (httpx) to call other agent APIs

**Key Features**:
- **Intent Analysis**: Uses Claude to understand user requests
- **Multi-Agent Orchestration**: Can trigger workflows, code generation, or remediation
- **Session Management**: Persists conversation history in DynamoDB
- **Web UI**: Accessible via browser at API Gateway root path
- **API Endpoints**:
  - POST /chat - Send messages
  - GET /session/{id} - Retrieve history
  - GET / - Serve web interface
  - GET /static/* - Serve CSS/JS assets

**Example Interactions**:
- "Create a new Python microservice with PostgreSQL"
- "Help me fix the failing CI/CD pipeline"
- "Generate a REST API with authentication"
- "What DevOps best practices should I follow?"

#### 7. Migration Agent (✅ Deployed)
**Purpose**: Converts Jenkins pipelines to GitHub Actions workflows automatically using AI-powered analysis.

**Responsibilities**:
- Parse Jenkins declarative and scripted pipelines
- Convert Jenkins stages and steps to GitHub Actions jobs
- Map Jenkins plugins to equivalent GitHub Actions
- Generate idiomatic GitHub Actions workflows
- Integrate with Jenkins servers for direct job migration
- Create GitHub repositories and push workflows
- Clean platform-specific commands (remove Windows commands from Linux workflows)

**Technology Stack**:
- Runtime: ECS Fargate (persistent service)
- AI Model: Claude API for intelligent pipeline analysis and conversion
- Languages: Python 3.11 with FastAPI
- Storage: Generates workflows and stores migration reports
- Integration: Jenkins REST API, GitHub REST API

**Key Features**:
- **LLM-Powered Parsing**: Uses Claude to intelligently parse complex Jenkinsfiles
- **Smart Conversion**: Generates optimized GitHub Actions workflows, not just direct translations
- **Jenkins Integration**: Connect to Jenkins servers to list, analyze, and migrate jobs
- **GitHub Integration**: Create repositories and commit workflows directly
- **Platform Cleanup**: Automatically removes platform-incompatible commands
- **Migration Reports**: Detailed reports of converted stages, environment variables, and triggers

**API Endpoints**:
- POST /migration/migrate - Convert Jenkinsfile to GitHub Actions
- POST /migration/analyze - Analyze Jenkins pipeline structure
- POST /migration/jenkins/test-connection - Test Jenkins server connection
- GET /migration/jenkins/list-jobs - List all Jenkins jobs
- POST /migration/jenkins/migrate-job - Migrate specific Jenkins job
- POST /migration/jenkins/create-job - Create new Jenkins job
- POST /migration/github/test-connection - Test GitHub connection
- POST /migration/test-integration - End-to-end integration test

**Example Migration Flow**:
```
Jenkins Pipeline → LLM Analysis → Structured Data → LLM Generation → GitHub Actions Workflow
     ↓                                                                        ↓
  Optional: Direct Jenkins integration                    Optional: Create GitHub repo + commit
```

**Conversion Capabilities**:
- **Stages**: Jenkins stages → GitHub Actions jobs
- **Steps**: Shell commands, Maven, Gradle, Docker, etc.
- **Environment**: Environment variables mapping
- **Agents**: Jenkins agents → GitHub Actions runners (ubuntu-latest, windows-latest, etc.)
- **Triggers**: cron, pollSCM → GitHub Actions triggers
- **Tools**: Java, Maven, Node.js → GitHub Actions setup actions
- **Post Actions**: success/failure actions → job status conditionals

**Version History**:
- v1.0.26 (Current): Fixed platform command cleanup integration
- v1.0.25: Added robust string handling for command cleanup
- v1.0.24: Enhanced logging for debugging
- v1.0.23: YAML-based cleanup with structured parsing
- v1.0.22: Initial LLM-powered migration with template fallback

**How the Migration Agent Converts Jenkins Pipelines to GitHub Actions**:

The Migration Agent uses a sophisticated AI-powered approach to convert Jenkins pipelines into idiomatic GitHub Actions workflows:

**Phase 1: Intelligent Parsing**
```
Jenkinsfile → LLM Analysis → Structured Pipeline Data
```

1. **LLM-Powered Parsing** (`parse_jenkinsfile_with_llm`):
   - Sends the Jenkinsfile to Claude API with detailed extraction instructions
   - Claude analyzes both declarative and scripted pipelines
   - Extracts: stages, steps, environment variables, triggers, tools, post-actions
   - Returns structured JSON representation of the pipeline
   - Falls back to regex-based parsing if LLM parsing fails

2. **Structured Data Extraction**:
   ```json
   {
     "type": "declarative",
     "agent": "ubuntu-latest",
     "stages": [
       {
         "name": "Build",
         "steps": ["./mvnw clean compile"]
       }
     ],
     "environment": {"JAVA_HOME": "/usr/lib/jvm/java-17"},
     "triggers": [{"type": "cron", "value": "H */4 * * 1-5"}],
     "tools": ["java", "maven"]
   }
   ```

**Phase 2: Intelligent Generation**
```
Structured Data → LLM Generation → GitHub Actions YAML
```

1. **LLM-Powered Generation** (`generate_workflow_with_llm`):
   - Sends structured pipeline data to Claude API
   - Instructs Claude to generate idiomatic GitHub Actions workflow
   - Claude intelligently:
     - Converts Jenkins stages to GitHub Actions jobs
     - Maps Jenkins steps to appropriate GitHub Actions
     - Selects optimal GitHub Actions from marketplace
     - Configures proper job dependencies
     - Adds best practices (caching, artifacts, etc.)

2. **Smart Conversion Examples**:

   **Jenkins Stage → GitHub Actions Job**:
   ```groovy
   // Jenkins
   stage('Build') {
     steps {
       sh './mvnw clean compile'
     }
   }
   ```
   ```yaml
   # GitHub Actions
   build:
     runs-on: ubuntu-latest
     steps:
       - uses: actions/checkout@v4
       - uses: actions/setup-java@v4
         with:
           java-version: '17'
           distribution: 'temurin'
           cache: 'maven'
       - name: Build
         run: ./mvnw clean compile
   ```

   **Jenkins Agent → GitHub Actions Runner**:
   ```groovy
   agent { label 'linux' }  →  runs-on: ubuntu-latest
   agent { label 'windows' } →  runs-on: windows-latest
   agent any                →  runs-on: ubuntu-latest (default)
   ```

   **Jenkins Tools → GitHub Actions Setup Actions**:
   ```groovy
   tools {
     jdk 'Java 17'
     maven 'Maven 3.9'
   }
   ```
   ```yaml
   - uses: actions/setup-java@v4
     with:
       java-version: '17'
       distribution: 'temurin'
       cache: 'maven'
   ```

**Phase 3: Platform Cleanup**
```
Generated Workflow → Platform Cleanup → Final Workflow
```

1. **Platform Command Cleanup** (`_clean_platform_commands`):
   - Parses generated YAML workflow
   - Identifies platform-specific commands
   - Removes incompatible commands based on runner type

2. **Cleanup Logic**:
   ```python
   # For Linux/Mac runners (ubuntu-latest, macos-latest)
   Remove: mvnw.cmd, gradlew.bat, .bat, .cmd, .exe, powershell
   Keep:   ./mvnw, ./gradlew, chmod, bash, sh

   # For Windows runners (windows-latest)
   Remove: ./mvnw, ./gradlew (unless .cmd/.bat/.exe)
   Keep:   mvnw.cmd, gradlew.bat, .bat, .cmd, .exe, powershell
   ```

3. **Example Cleanup**:
   ```yaml
   # Before Cleanup (Windows commands on Linux runner)
   - name: Build
     run: mvnw.cmd clean compile  # ❌ Will fail on ubuntu-latest
   - name: Build
     run: ./mvnw clean compile    # ✅ Works on ubuntu-latest

   # After Cleanup
   - name: Build
     run: ./mvnw clean compile    # ✅ Only compatible command remains
   ```

**Phase 4: Enhanced Features**

1. **Automatic Optimizations**:
   - Adds dependency caching (Maven, Gradle, npm)
   - Configures artifact uploads for build outputs
   - Sets up proper checkout with correct repository/branch
   - Adds job concurrency controls
   - Configures timeout values

2. **Trigger Conversion**:
   ```groovy
   // Jenkins
   triggers {
     cron('H */4 * * 1-5')      →  schedule: '0 */4 * * 1-5'
     pollSCM('H/15 * * * *')    →  push: branches: [main]
   }
   ```

3. **Post Actions → Job Status**:
   ```groovy
   // Jenkins
   post {
     success { echo 'Success!' }
     failure { echo 'Failed!' }
   }
   ```
   ```yaml
   # GitHub Actions
   - name: Success message
     if: success()
     run: echo 'Success!'
   - name: Failure message
     if: failure()
     run: echo 'Failed!'
   ```

**Complete Example Flow**:

```
Input Jenkinsfile:
─────────────────
pipeline {
  agent any
  tools { jdk 'Java 17' }
  stages {
    stage('Build') {
      steps {
        sh './mvnw clean compile'
        sh 'mvnw.cmd clean compile'  // Windows command
      }
    }
  }
}

↓ LLM Parsing ↓

Structured Data:
────────────────
{
  "agent": "ubuntu-latest",
  "tools": ["java"],
  "stages": [
    {"name": "Build", "steps": ["./mvnw clean compile", "mvnw.cmd clean compile"]}
  ]
}

↓ LLM Generation ↓

Generated Workflow:
───────────────────
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
      - run: ./mvnw clean compile
      - run: mvnw.cmd clean compile  # Windows command

↓ Platform Cleanup ↓

Final Workflow:
───────────────
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
          cache: 'maven'
      - run: ./mvnw clean compile     # ✅ Windows command removed
```

**Why This Approach Works**:

1. **Intelligence Over Templates**: LLM understands context and intent, not just syntax
2. **Idiomatic Output**: Generates GitHub Actions workflows that follow best practices
3. **Handles Complexity**: Can parse complex scripted pipelines with conditional logic
4. **Platform Awareness**: Automatically removes incompatible platform commands
5. **Optimization**: Adds caching, artifacts, and other GitHub Actions features automatically

#### 8. Observability Agent (Planned)
**Purpose**: Analyzes telemetry data and provides intelligent insights into system health.

**Responsibilities**:
- Aggregate metrics, logs, and traces from OpenTelemetry
- Detect anomalies using ML-based analysis
- Generate operational summaries and reports
- Predict potential failures before they occur
- Trigger alerts and remediation workflows

**Technology Stack**:
- Runtime: ECS Fargate (persistent service)
- Data Store: AWS CloudWatch, S3 (long-term storage)
- Analytics: AWS SageMaker for anomaly detection models
- Visualization: Grafana dashboards
- AI Model: Claude API for natural language summaries

**Key Metrics**:
- Deployment frequency and success rate
- Mean Time to Recovery (MTTR)
- Change failure rate
- Service availability (SLA compliance)

---

## AWS Infrastructure

### Compute Layer

#### AWS Lambda
- **Use Case**: Event-driven, short-lived agent tasks (Planner, CodeGen, Policy)
- **Configuration**:
  - Runtime: Python 3.11 or Node.js 18
  - Memory: 2GB - 10GB (based on AI model requirements)
  - Timeout: 15 minutes (max)
  - VPC: Enabled for secure resource access
- **Scaling**: Automatic based on EventBridge event rate
- **Cost Optimization**: Reserved concurrency for predictable workloads

#### Amazon ECS Fargate
- **Use Case**: Long-running agents (Deployment, Remediation, Observability)
- **Configuration**:
  - Task CPU: 2-4 vCPU
  - Task Memory: 8-16 GB
  - Auto-scaling: Target tracking based on CPU/memory
- **Networking**: Deployed in private subnets with NAT Gateway egress
- **High Availability**: Multi-AZ deployment with Application Load Balancer

#### Amazon EKS
- **Use Case**: Target deployment platform for customer applications
- **Configuration**:
  - Kubernetes Version: 1.28+
  - Node Groups: Mixed (spot + on-demand)
  - Add-ons: AWS Load Balancer Controller, EBS CSI Driver, CoreDNS
- **GitOps**: ArgoCD installed as cluster operator
- **Observability**: OpenTelemetry Collector deployed as DaemonSet

### Messaging & Events

#### AWS EventBridge
- **Purpose**: Central event bus for agent communication
- **Event Patterns**:
  ```json
  {
    "source": "agentic-framework",
    "detail-type": [
      "task.created",
      "deployment.completed",
      "policy.violated",
      "anomaly.detected"
    ]
  }
  ```
- **Rules**: Route events to Lambda, SQS, or ECS tasks
- **Dead Letter Queue**: SQS for failed event processing

#### Amazon SQS
- **Purpose**: Task queues for asynchronous agent work
- **Queues**:
  - `codegen-tasks.fifo`: Ordered code generation tasks
  - `deployment-tasks`: Deployment operations
  - `remediation-tasks`: Auto-remediation actions
- **Configuration**:
  - Visibility Timeout: 15 minutes
  - Dead Letter Queue: After 3 retries

### Storage Layer

#### Amazon S3
**Buckets**:
1. `agent-artifacts-{env}`: Generated code, IaC, configs
2. `policy-bundles-{env}`: OPA policies, Kyverno rules
3. `telemetry-archive-{env}`: Long-term log/metric storage
4. `terraform-state-{env}`: Remote backend for Terraform

**Security**:
- Bucket encryption: AES-256 or KMS
- Versioning: Enabled for audit trails
- Access: IAM roles only, no public access

#### Amazon DynamoDB
**Tables**:
1. `workflows`: Planner Agent workflow state
   - PK: `workflow_id`, SK: `task_id`
   - GSI: `status-index` for querying active workflows
2. `deployments`: Deployment history
   - PK: `deployment_id`, SK: `timestamp`
   - TTL: 90 days for old records
3. `policy-violations`: Audit log
   - PK: `violation_id`, SK: `timestamp`

**Configuration**:
- Billing Mode: On-demand (unpredictable workloads)
- Point-in-time Recovery: Enabled
- Encryption: AWS-managed keys

#### AWS Secrets Manager
**Purpose**: Centralized secret storage for all agents and applications

**Secrets Stored**:
- GitLab API tokens
- ArgoCD admin credentials
- Database connection strings
- API keys for external services (Claude API, DataDog)

**Rotation**: Automated 90-day rotation for database credentials

### API Layer

#### Amazon API Gateway
- **Type**: HTTP API (lower cost, better performance than REST API)
- **Endpoints**:
  - `POST /workflows` - Create new workflow (triggers Planner)
  - `GET /workflows/{id}` - Query workflow status
  - `POST /deploy` - Manual deployment trigger
  - `GET /health` - Agent health check
- **Authentication**: AWS IAM or JWT (from Backstage)
- **Rate Limiting**: 1000 requests/second per account
- **Integration**: Direct integration with Lambda and EventBridge

---

## Data Flow & Orchestration

### End-to-End Workflow Example

**Scenario**: Developer creates a new microservice via Backstage

```
1. Developer Request
   └─> Backstage UI
       └─> POST /workflows to API Gateway
           └─> Planner Agent (Lambda)
               ├─> Stores workflow in DynamoDB
               └─> Publishes events to EventBridge

2. Code Generation Phase
   └─> EventBridge Rule: "task.created" + "detail.agent = codegen"
       └─> Triggers CodeGen Agent (Lambda)
           ├─> Generates code from templates
           ├─> Stores artifacts in S3
           ├─> Pushes to GitLab repository
           └─> Publishes "codegen.completed" event

3. CI/CD Pipeline
   └─> GitLab webhook triggers CI pipeline
       ├─> Runs unit tests
       ├─> Builds Docker image
       ├─> Pushes to ECR
       └─> Updates ArgoCD manifest in Git

4. Policy Validation
   └─> EventBridge Rule: "codegen.completed"
       └─> Triggers Policy Agent (Lambda)
           ├─> Runs OPA policies on Terraform
           ├─> Scans Docker image with Trivy
           ├─> Checks for secrets in code
           └─> Publishes "policy.validated" or "policy.violated"

5. Infrastructure Provisioning
   └─> If policy passes:
       └─> Deployment Agent (ECS Fargate)
           ├─> Runs Terraform apply
           ├─> Creates RDS, S3, IAM resources
           ├─> Updates state in DynamoDB
           └─> Publishes "infra.provisioned" event

6. Application Deployment
   └─> ArgoCD detects Git manifest changes
       ├─> Syncs application to EKS cluster
       ├─> Monitors pod health
       └─> Sends status to Deployment Agent via webhook

7. Observability Check
   └─> Observability Agent (ECS Fargate)
       ├─> Queries metrics from Prometheus
       ├─> Validates SLOs (latency, error rate)
       ├─> Generates deployment summary
       └─> Posts results to Backstage UI

8. Workflow Completion
   └─> Planner Agent marks workflow complete
       └─> Sends notification to developer via Slack/email
```

### Event Schema Definitions

#### Workflow Created Event
```json
{
  "source": "agentic-framework.planner",
  "detail-type": "workflow.created",
  "detail": {
    "workflow_id": "wf-12345",
    "requested_by": "user@example.com",
    "service_name": "user-service",
    "template": "rest-api-postgres",
    "environment": "staging",
    "tasks": [
      {"task_id": "t1", "agent": "codegen", "priority": 1},
      {"task_id": "t2", "agent": "deployment", "priority": 2}
    ]
  }
}
```

#### Deployment Completed Event
```json
{
  "source": "agentic-framework.deployment",
  "detail-type": "deployment.completed",
  "detail": {
    "deployment_id": "dep-67890",
    "workflow_id": "wf-12345",
    "service_name": "user-service",
    "environment": "staging",
    "version": "v1.2.3",
    "status": "success",
    "duration_seconds": 120,
    "argocd_sync_id": "abc123"
  }
}
```

---

## Integration Architecture

### GitLab Integration
**Purpose**: Source control and CI/CD orchestration

**Integration Points**:
1. **Repository Management**: CodeGen Agent creates repos via GitLab API
2. **CI Pipelines**: Scaffolding Agent generates `.gitlab-ci.yml`
3. **Webhooks**: Push events trigger policy checks and deployments
4. **Merge Requests**: Policy Agent comments on MRs with security findings

**Authentication**: Project access tokens stored in Secrets Manager

### ArgoCD Integration
**Purpose**: GitOps-based Kubernetes deployments

**Integration Points**:
1. **Application Sync**: Deployment Agent creates ArgoCD Application resources
2. **Health Checks**: Queries ArgoCD API for deployment status
3. **Rollbacks**: Automated rollback on failed health checks
4. **Notifications**: Webhook to Observability Agent on sync events

**Configuration**:
- Sync Policy: Automated with self-heal enabled
- Prune Resources: Enabled for clean state
- Repo: GitLab (manifest repositories)

### Backstage Integration
**Purpose**: Developer portal and service catalog

**Integration Points**:
1. **Service Creation**: Software templates trigger Planner Agent workflows
2. **Status Dashboard**: Real-time workflow progress from DynamoDB
3. **Documentation**: Auto-generated docs from CodeGen Agent
4. **Compliance View**: Policy violation reports embedded in service pages

**Plugins**:
- `agentic-framework-backend`: API proxy to framework endpoints
- `agentic-workflow-frontend`: React components for workflow UI

### OpenTelemetry Integration
**Purpose**: Unified observability standard

**Architecture**:
```
Application Pods (EKS)
  └─> OTel SDK
      └─> OTel Collector (DaemonSet)
          ├─> AWS CloudWatch (metrics/logs)
          ├─> AWS X-Ray (traces)
          └─> EventBridge (anomaly events)
              └─> Observability Agent
```

**Instrumentation**:
- Auto-instrumentation for Python, Node.js, Java via OTel operators
- Custom metrics for business KPIs
- Trace context propagation across agents

---

## Security & Governance

### Security Architecture

#### Identity & Access Management
1. **Agent IAM Roles**: Each agent has minimal IAM permissions
   - Planner: DynamoDB write, EventBridge publish
   - CodeGen: S3 write, GitLab API (via Secrets Manager)
   - Deployment: EKS/ECS describe, Terraform execution role
2. **Service Accounts**: Kubernetes RBAC for pod-level permissions
3. **API Authentication**: AWS Signature V4 for API Gateway

#### Network Security
- **VPC Design**: Private subnets for agents, public subnets for load balancers
- **Security Groups**: Least-privilege inbound/outbound rules
- **NAT Gateway**: Controlled egress for external API calls
- **PrivateLink**: AWS service access without internet gateway

#### Secret Management
- **Encryption**: All secrets encrypted with KMS
- **Access Logging**: CloudTrail logs all secret retrievals
- **Rotation**: Automated 90-day rotation for database/API credentials
- **Dynamic Secrets**: Generated on-demand for Terraform runs

### Policy Enforcement

#### Pre-Deployment Checks
```
┌─────────────────────────────────────────┐
│         Pull Request Created            │
└───────────────┬─────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│      Policy Agent Triggered             │
│                                         │
│  1. Terraform Plan Analysis (tfsec)    │
│  2. Dockerfile Security Scan (Trivy)   │
│  3. OPA Policy Evaluation               │
│  4. Secret Detection (git-secrets)      │
│  5. License Compliance Check            │
└───────────────┬─────────────────────────┘
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
   [PASS]           [FAIL]
        │                │
        │                └─> Block merge + Comment on PR
        │
        └─> Allow merge
```

#### Runtime Enforcement (Kyverno)
- **Admission Control**: Enforce pod security standards
- **Mutation**: Auto-inject sidecar containers (OTel, security agents)
- **Validation**: Require resource limits, specific image registries

#### Compliance Reporting
- **Quarterly Reports**: Generated by Policy Agent and stored in S3
- **Audit Trails**: All policy violations logged to DynamoDB
- **Metrics**: Policy compliance rate tracked in CloudWatch

---

## Observability & Monitoring

### Telemetry Pipeline

```
┌──────────────────────────────────────────────────────┐
│              Data Sources                            │
├──────────────┬───────────────┬───────────────────────┤
│   Agents     │  Applications │   Infrastructure      │
│  (Lambda,    │   (EKS Pods)  │   (ECS, RDS, EKS)    │
│   ECS)       │               │                       │
└──────┬───────┴───────┬───────┴─────────┬─────────────┘
       │               │                 │
       └───────────────┼─────────────────┘
                       │
                       ▼
       ┌───────────────────────────────┐
       │   OpenTelemetry Collector     │
       │   (EKS DaemonSet + ECS Task) │
       └───────────────┬───────────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
         ▼             ▼             ▼
    ┌────────┐   ┌─────────┐   ┌─────────┐
    │CloudWat│   │AWS X-Ray│   │EventBrid│
    │  ch    │   │         │   │   ge    │
    └────┬───┘   └────┬────┘   └────┬────┘
         │            │             │
         └────────────┼─────────────┘
                      │
                      ▼
         ┌────────────────────────────┐
         │   Observability Agent      │
         │   - Anomaly Detection      │
         │   - Alerting Logic         │
         │   - AI Summarization       │
         └────────────┬───────────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
         ▼            ▼            ▼
    ┌────────┐  ┌─────────┐  ┌─────────┐
    │Grafana │  │Backstage│  │  Slack  │
    │Dashbord│  │   UI    │  │Notificat│
    └────────┘  └─────────┘  └─────────┘
```

### Key Observability Features

#### 1. Agent Health Monitoring
- **Metrics**: Invocation count, error rate, duration
- **Alarms**: CloudWatch alarms for Lambda errors > 5%
- **Dashboards**: Grafana dashboard showing agent performance

#### 2. Deployment Analytics
- **DORA Metrics**: Deployment frequency, lead time, MTTR, change failure rate
- **Visualization**: Backstage plugin showing trends over time
- **AI Insights**: Weekly summaries generated by Observability Agent

#### 3. Anomaly Detection
- **ML Models**: SageMaker models trained on historical metrics
- **Detection**: Real-time anomaly detection (e.g., sudden spike in errors)
- **Response**: Automatic alert to Remediation Agent

#### 4. Cost Observability
- **AWS Cost Explorer**: Track spending by agent, service, environment
- **Budget Alerts**: SNS notifications when exceeding thresholds
- **Optimization**: Recommendations from Observability Agent

---

## Developer Experience

### Backstage Software Templates

#### Template: Microservice with Database
```yaml
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: microservice-with-db
  title: Microservice with PostgreSQL
spec:
  parameters:
    - title: Service Details
      properties:
        serviceName:
          type: string
        language:
          type: string
          enum: [python, nodejs, go]
        database:
          type: string
          enum: [postgresql, dynamodb]
  steps:
    - id: trigger-planner
      action: http:post
      input:
        url: https://api.example.com/workflows
        body:
          template: microservice-db
          params: ${{ parameters }}
```

### Self-Service Capabilities
1. **Create Service**: 5-minute onboarding from template to deployed
2. **View Pipelines**: Embedded GitLab CI status
3. **Check Compliance**: Real-time policy validation results
4. **Request Resources**: One-click database, cache, storage provisioning

### Documentation Generation
- **README.md**: Auto-generated with setup instructions
- **API Docs**: OpenAPI spec generated from code annotations
- **Architecture Diagrams**: Backstage TechDocs with Mermaid diagrams

---

## Deployment Strategy

### Multi-Environment Setup

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│     Dev     │───▶│   Staging   │───▶│  Production │
│             │    │             │    │             │
│ - Fast iter │    │ - QA tests  │    │ - Blue-Green│
│ - No policy │    │ - Policy on │    │ - Full policy
│ - Manual    │    │ - Auto-deploy   │ - Approval   │
└─────────────┘    └─────────────┘    └─────────────┘
```

#### Environment Characteristics
| Environment | Deployment | Policy | Observability |
|-------------|-----------|--------|---------------|
| Dev         | On every commit | Advisory only | Basic |
| Staging     | On merge to main | Enforced | Full |
| Production  | Manual approval | Strictly enforced | Full + anomaly detection |

### Infrastructure as Code

#### Terraform Module Structure
```
/iac
  /modules
    /agent-lambda      # Reusable Lambda agent module
    /ecs-agent        # Reusable ECS agent module
    /eventbridge      # Event bus configuration
    /networking       # VPC, subnets, security groups
  /environments
    /dev
      main.tf
      variables.tf
    /staging
    /production
```

#### Helm Charts for EKS
```
/helm
  /charts
    /otel-collector
    /argocd-applications
    /backstage
```

---

## API Specifications

### Planner Agent API

#### Create Workflow
```http
POST /workflows
Content-Type: application/json
Authorization: Bearer {token}

{
  "requestedBy": "user@example.com",
  "template": "microservice-rest-api",
  "parameters": {
    "serviceName": "user-service",
    "language": "python",
    "database": "postgresql",
    "environment": "staging"
  }
}

Response: 201 Created
{
  "workflowId": "wf-12345",
  "status": "in_progress",
  "tasks": [
    {
      "taskId": "t1",
      "agent": "codegen",
      "status": "pending",
      "estimatedDuration": "2m"
    }
  ]
}
```

#### Query Workflow Status
```http
GET /workflows/{workflowId}

Response: 200 OK
{
  "workflowId": "wf-12345",
  "status": "completed",
  "completedAt": "2024-12-01T10:30:00Z",
  "duration": "5m32s",
  "tasks": [...]
}
```

### Deployment Agent API

#### Trigger Deployment
```http
POST /deploy
Content-Type: application/json

{
  "service": "user-service",
  "version": "v1.2.3",
  "environment": "staging",
  "strategy": "rolling"
}

Response: 202 Accepted
{
  "deploymentId": "dep-67890",
  "status": "deploying",
  "argocdAppUrl": "https://argocd.example.com/applications/user-service"
}
```

### Policy Agent API

#### Validate Policy
```http
POST /policy/validate
Content-Type: application/json

{
  "type": "terraform_plan",
  "content": "... base64-encoded Terraform plan ..."
}

Response: 200 OK
{
  "valid": false,
  "violations": [
    {
      "severity": "high",
      "rule": "no-public-s3-buckets",
      "message": "S3 bucket 'example-bucket' is publicly accessible"
    }
  ]
}
```

---

## Scaling & Performance

### Horizontal Scaling

#### Lambda Agents
- **Concurrent Executions**: Up to 1000 (default account limit)
- **Reserved Concurrency**: 100 for Planner Agent (critical path)
- **Scaling**: Automatic based on event rate

#### ECS Agents
- **Auto-scaling Policy**: Target 70% CPU utilization
- **Min Tasks**: 2 (high availability)
- **Max Tasks**: 10 (cost control)

### Performance Targets

| Agent | p50 Latency | p99 Latency | Throughput |
|-------|------------|-------------|------------|
| Planner | < 500ms | < 2s | 100 workflows/min |
| CodeGen | < 10s | < 30s | 50 generations/min |
| Deployment | < 5m | < 15m | 20 deployments/min |
| Policy | < 2s | < 5s | 500 validations/min |

### Cost Optimization
1. **Lambda**: Use ARM64 architecture (20% cost savings)
2. **ECS**: Mix of Spot (70%) and On-Demand (30%) instances
3. **S3**: Lifecycle policies to move old artifacts to Glacier
4. **DynamoDB**: On-demand billing for unpredictable workloads

---

## Future Enhancements

### Planned Features
1. **Multi-Cloud Support**: Extend agents to support Azure and GCP
2. **Advanced AI Models**: Fine-tune custom models for domain-specific tasks
3. **Predictive Scaling**: ML-based prediction of resource needs
4. **Self-Healing Infrastructure**: Automated drift remediation
5. **Natural Language Interface**: Chat-based interaction with agents via Slack

### Extensibility
- **Custom Agents**: Plugin architecture for organization-specific agents
- **Template Marketplace**: Community-contributed Backstage templates
- **Policy Packs**: Shareable OPA policy bundles

---

## Appendix

### Glossary
- **Agent**: Autonomous AI-driven service responsible for a specific domain
- **GitOps**: Declarative infrastructure and application management using Git
- **OPA**: Open Policy Agent, policy engine for authorization decisions
- **DORA**: DevOps Research and Assessment, metrics for software delivery performance

### References
- [AWS Lambda Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [ArgoCD Operator Manual](https://argo-cd.readthedocs.io/)
- [Backstage Software Templates](https://backstage.io/docs/features/software-templates/)

### Contact & Support
- **GitHub**: https://github.com/darrylbowler72/agenticframework
- **Issues**: Submit via GitHub Issues
- **Discussions**: GitHub Discussions for Q&A

---

*Last Updated: 2025-12-11*
*Version: 1.1.1*
