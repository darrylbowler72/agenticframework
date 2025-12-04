# DevOps Agentic Framework

## Overview
The **DevOps Agentic Framework** provides an autonomous, AI-driven platform that accelerates software delivery by integrating multi-agent automation, GitOps workflows, policy enforcement, and developer experience tooling.

## Current Status
**✅ DEPLOYED AND RUNNING**

The framework infrastructure is currently deployed in AWS with the following components:

### Active Services
- **3 AI Agent Services** running on AWS ECS Fargate:
  - Planner Agent (port 8000) - Orchestrates multi-step workflows
  - CodeGen Agent (port 8001) - Generates code and infrastructure templates
  - Remediation Agent (port 8002) - Automatically fixes detected issues

- **Infrastructure Components**:
  - AWS API Gateway for agent orchestration
  - DynamoDB tables for workflow and deployment state
  - S3 buckets for artifacts, templates, and policy bundles
  - EventBridge for event-driven agent communication
  - CloudWatch for logging and monitoring
  - Secrets Manager for secure credential storage

## Key Capabilities
- **AI Scaffolding** – Generates repos, microservice templates, IaC, CI/CD, and manifests automatically.
- **Multi-Agent System** – Planner, CodeGen, and Remediation agents powered by Claude AI.
- **GitOps Delivery** – Declarative deployments with ArgoCD (planned).
- **Policy Automation** – OPA and Kyverno-backed governance and compliance checks (planned).
- **Observability Intelligence** – OTel-driven anomaly detection and operational summaries (planned).
- **Developer Experience Hub** – Backstage integration for unified workflows (planned).

## AWS Architecture Components

### Deployed Infrastructure
- **Compute**: ECS Fargate cluster running 3 agent services
- **Messaging**: AWS EventBridge for event-driven orchestration
- **Storage**:
  - S3: Agent artifacts, codegen templates, policy bundles, Terraform state
  - DynamoDB: Workflows, deployments, policy violations
- **Integration**: API Gateway HTTP API for agent endpoints
- **Security**: AWS Secrets Manager for API keys and credentials
- **Monitoring**: CloudWatch Logs and metrics

### Planned Components
- **EKS**: Kubernetes cluster for application workloads
- **GitLab Integration**: CI/CD pipeline orchestration
- **ArgoCD**: GitOps-based deployment automation
- **Backstage**: Developer portal and service catalog

## Project Structure
```
/backend/agents      # AI agent implementations (Python)
  /planner          # Workflow orchestration agent
  /codegen          # Code generation agent
  /remediation      # Auto-remediation agent
/iac                # Infrastructure as Code
  /terraform        # AWS infrastructure modules
    /modules        # Reusable Terraform modules
    /environments   # Environment-specific configs
/scripts            # Deployment automation scripts
/docs               # Documentation
/user-stories       # Product requirements
```

## Getting Started

### Prerequisites
- AWS Account with appropriate permissions
- AWS CLI configured
- Terraform >= 1.0
- Podman or Docker
- Anthropic API key

### Quick Deploy
The framework includes automated deployment scripts:

1. **Configure AWS Credentials**
   ```bash
   # Copy example environment file
   cp .env.example .env

   # Edit .env with your AWS credentials and Anthropic API key
   ```

2. **Set Up Terraform Backend**
   ```bash
   bash scripts/02-setup-aws-backend.sh
   ```

3. **Deploy Infrastructure**
   ```bash
   bash scripts/03-deploy-infrastructure.sh
   ```

4. **Store API Secrets**
   ```bash
   # Store your Anthropic API key in AWS Secrets Manager
   aws secretsmanager put-secret-value \
     --secret-id dev-anthropic-api-key \
     --secret-string "your-api-key-here"
   ```

5. **Build and Deploy Agent Containers**
   ```bash
   bash scripts/05-deploy-agents-podman.sh
   ```

### Verify Deployment
Check that all services are running:
```bash
aws ecs list-services --cluster dev-agentic-cluster --region us-east-1
```

### Access API Gateway
Get your API Gateway endpoint:
```bash
cd iac/terraform
terraform output api_gateway_url
```

## Example Workflow
1. Developer sends request to API Gateway endpoint
2. Planner Agent receives request and decomposes into tasks
3. Tasks published to EventBridge
4. Specialized agents (CodeGen, Remediation) process their tasks
5. Results stored in DynamoDB and S3
6. Workflow status available via API

## Documentation
- [Architecture Documentation](./architecture.md) - Detailed system architecture
- [Deployment Guide](./DEPLOYMENT.md) - Step-by-step deployment instructions
- [User Stories](./user-stories/README.md) - Product requirements and use cases

## Current Deployment
**Environment**: Development
**Region**: us-east-1
**Infrastructure**: 70+ AWS resources deployed via Terraform
**Agents**: 3 ECS services running on Fargate

## Next Steps
1. Configure GitLab integration for CI/CD
2. Deploy ArgoCD for GitOps workflows
3. Set up Backstage developer portal
4. Implement Policy Agent with OPA
5. Add Observability Agent with OpenTelemetry

## Contributing
Issues and PRs are welcome.

## License
MIT License
