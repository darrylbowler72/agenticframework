# User Story: Implement Backstage Software Template for Microservice Scaffolding

## Epic
Application Development Scaffolding

## Story
**As a** developer
**I want** to create a new microservice with all necessary boilerplate code, infrastructure, and CI/CD pipelines through a Backstage template
**So that** I can start building business logic immediately without spending time on setup and configuration

## Priority
**High** - Core feature for developer productivity

## Acceptance Criteria

### Must Have
- [ ] Backstage software template is created and registered in the catalog
- [ ] Template form collects required parameters:
  - Service name (with validation for naming conventions)
  - Programming language (Python, Node.js, Go)
  - Database type (PostgreSQL, DynamoDB, None)
  - API type (REST, gRPC, GraphQL)
  - Target environment (dev, staging, production)
- [ ] Template triggers Planner Agent via API Gateway endpoint
- [ ] Developer receives workflow ID and can track progress in Backstage UI
- [ ] Generated repository includes:
  - Application code with basic CRUD endpoints
  - Dockerfile and docker-compose.yml
  - README.md with setup instructions
  - .gitignore with appropriate exclusions
- [ ] Infrastructure as Code (Terraform) is generated:
  - VPC and networking (if new service)
  - Database resources (RDS or DynamoDB)
  - IAM roles and policies
  - Secrets Manager entries
- [ ] CI/CD pipeline configuration is created:
  - GitLab CI or GitHub Actions workflow
  - Build, test, scan, and deploy stages
  - Environment-specific deployment jobs
- [ ] Kubernetes manifests are generated:
  - Deployment, Service, Ingress resources
  - ConfigMap and Secret references
  - HPA (Horizontal Pod Autoscaler) configuration

### Should Have
- [ ] Template supports advanced options (collapsed by default):
  - Redis cache integration
  - Message queue (SQS/SNS)
  - Scheduled jobs (cron)
  - Authentication method (JWT, OAuth2)
- [ ] Generated code includes:
  - Unit test scaffolding with sample tests
  - OpenTelemetry instrumentation pre-configured
  - Health check endpoints (/health, /ready)
  - Graceful shutdown handling
- [ ] ArgoCD Application manifest is created and committed to GitOps repo

### Could Have
- [ ] Template preview showing directory structure before generation
- [ ] Ability to customize templates per organization
- [ ] Template versioning (allow developers to choose template version)

## Technical Implementation Notes

### Architecture Components
```
Backstage UI
  └─> Software Template (YAML)
      └─> HTTP POST to API Gateway (/workflows)
          └─> Planner Agent (Lambda)
              ├─> Publishes "task.created" event
              └─> EventBridge routes to CodeGen Agent
                  ├─> Retrieves templates from S3
                  ├─> Renders templates with parameters
                  ├─> Creates GitLab repository
                  ├─> Pushes generated code
                  └─> Updates Backstage catalog
```

### Backstage Template Structure
```yaml
apiVersion: scaffolder.backstage.io/v1beta3
kind: Template
metadata:
  name: microservice-with-database
  title: Microservice with Database
  description: Create a new microservice with REST API and database
spec:
  owner: platform-team
  type: service
  parameters:
    - title: Service Information
      required:
        - serviceName
        - language
      properties:
        serviceName:
          type: string
          description: Name of the service (kebab-case)
          pattern: '^[a-z][a-z0-9-]*$'
        language:
          type: string
          enum: [python, nodejs, go]
          default: python
        database:
          type: string
          enum: [postgresql, dynamodb, none]
          default: postgresql
  steps:
    - id: trigger-planner
      name: Trigger Planner Agent
      action: http:backstage:request
      input:
        method: POST
        path: /workflows
        body:
          template: microservice-rest-api
          parameters: ${{ parameters }}
```

### CodeGen Agent Implementation
- **Language**: Python 3.11
- **Framework**: AWS Lambda with Claude API integration
- **Template Engine**: Jinja2
- **Template Storage**: S3 bucket (`codegen-templates-{env}`)
- **Output Storage**: S3 bucket (`agent-artifacts-{env}`)

### API Endpoint
```
POST /workflows
Authorization: Bearer {backstage-jwt}
Content-Type: application/json

{
  "template": "microservice-rest-api",
  "parameters": {
    "serviceName": "user-service",
    "language": "python",
    "database": "postgresql",
    "apiType": "rest",
    "environment": "staging"
  }
}
```

### Database Schema (DynamoDB)
**Table**: `workflows`
- PK: `workflow_id` (String)
- SK: `task_id` (String)
- Attributes: `status`, `agent`, `created_at`, `completed_at`, `output_url`

## Dependencies
- [ ] API Gateway endpoint configured
- [ ] Planner Agent Lambda deployed
- [ ] CodeGen Agent Lambda deployed
- [ ] S3 buckets created for templates and artifacts
- [ ] DynamoDB table `workflows` created
- [ ] GitLab API token stored in Secrets Manager
- [ ] Backstage backend plugin for API communication

## Testing Strategy
1. **Unit Tests**:
   - Template parameter validation
   - Jinja2 rendering with various inputs
   - GitLab API client mock tests
2. **Integration Tests**:
   - End-to-end workflow from Backstage to generated repo
   - Verify all files are created correctly
   - Validate generated Terraform syntax
3. **Manual Tests**:
   - Create service via Backstage UI
   - Clone generated repository
   - Run `docker-compose up` to verify application starts
   - Deploy to dev environment and test endpoints

## Estimated Effort
**8-10 story points** (2-3 weeks for 1 developer)

### Breakdown
- Backstage template development: 2 days
- Planner Agent implementation: 3 days
- CodeGen Agent with template rendering: 5 days
- Template creation (Python, Node.js, Go): 4 days
- Testing and refinement: 3 days

## Success Metrics
- Time to create new service: < 5 minutes (from template form to deployed service)
- Developer satisfaction score: > 4.5/5
- Template usage: 80% of new services use scaffolding
- Reduction in setup-related support tickets: > 70%

## Related Issues
- #TBD: Implement Planner Agent Lambda
- #TBD: Implement CodeGen Agent Lambda
- #TBD: Create service template library (Python, Node.js, Go)
- #TBD: Deploy API Gateway and EventBridge infrastructure

## Documentation
- Update architecture.md with Backstage integration details
- Create developer guide: "Creating a New Service with Scaffolding"
- Record video walkthrough of template usage
- Update Backstage docs with template catalog

## Labels
`enhancement`, `scaffolding`, `backstage`, `codegen-agent`, `high-priority`
