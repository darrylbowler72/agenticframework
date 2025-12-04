# DevOps Agentic Framework - Current Deployment Status

**Last Updated**: 2024-12-04
**Environment**: Development (dev)
**Region**: us-east-1
**Status**: ✅ **FULLY OPERATIONAL WITH API GATEWAY INTEGRATION**

---

## Deployment Summary

The DevOps Agentic Framework is now **fully deployed and accessible** via API Gateway. All components are operational and integrated.

### What's New (Latest Deployment)
- ✅ Application Load Balancer created and configured
- ✅ VPC Link established between API Gateway and private ECS services
- ✅ API Gateway routes configured for all agent endpoints
- ✅ ECS services registered with ALB target groups
- ✅ Health check endpoints configured and monitored

---

## Infrastructure Components

### 1. API Gateway (Publicly Accessible)
**Endpoint**: `https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev`

#### Available Routes:
- `POST /workflows` - Create new workflow (Planner Agent)
- `GET /workflows/{workflow_id}` - Get workflow status
- `POST /generate` - Generate microservice code (CodeGen Agent)
- `POST /remediate` - Auto-remediate issues (Remediation Agent)
- `GET /planner/health` - Planner Agent health check
- `GET /codegen/health` - CodeGen Agent health check
- `GET /remediation/health` - Remediation Agent health check

### 2. Application Load Balancer
**Type**: Internal ALB
**Name**: dev-agents-alb
**Subnets**: 3 private subnets across 2 AZs
**Security**: ALB Security Group with VPC-only access

#### Target Groups:
- **dev-planner-tg** (port 8000) - Routes to Planner Agent containers
- **dev-codegen-tg** (port 8001) - Routes to CodeGen Agent containers
- **dev-remediation-tg** (port 8002) - Routes to Remediation Agent containers

### 3. ECS Services (Running on Fargate)
All services running in private subnets, registered with ALB:

| Service | Status | Port | Container Image | Resources |
|---------|--------|------|----------------|-----------|
| dev-planner-agent | ✅ Running | 8000 | planner-agent:latest | 512 CPU / 1024 MB |
| dev-codegen-agent | ✅ Running | 8001 | codegen-agent:latest | 512 CPU / 1024 MB |
| dev-remediation-agent | ✅ Running | 8002 | remediation-agent:latest | 512 CPU / 1024 MB |

### 4. VPC Link
**Name**: dev-vpc-link
**Purpose**: Connects API Gateway (public) to ALB (private VPC)
**Subnets**: 3 private subnets
**Status**: ✅ Active

### 5. Supporting Infrastructure

#### DynamoDB Tables:
- `dev-workflows` - Workflow orchestration state
- `dev-remediation-actions` - Remediation tracking
- `dev-remediation-playbooks` - Remediation procedures
- `dev-chatbot-sessions` - Session management

#### S3 Buckets:
- `dev-agent-artifacts-773550624765` - Generated code and artifacts
- `dev-codegen-templates-773550624765` - Code generation templates
- `dev-policy-bundles-773550624765` - Policy definitions
- `dev-terraform-state-773550624765` - Terraform state (managed separately)

#### Secrets Manager:
- `dev-anthropic-api-key` - Claude API credentials
- `dev-gitlab-credentials` - GitLab integration
- `dev-slack-credentials` - Slack notifications

#### EventBridge:
- Custom event bus: `dev-agentic-framework`
- Event rules for task orchestration
- SQS dead letter queue for failed events

#### CloudWatch:
- Log groups for all services
- API Gateway access logs
- ECS container logs

---

## Usage Examples

### 1. Test Health Endpoints

```bash
# Test Planner Agent
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/planner/health

# Test CodeGen Agent
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/codegen/health

# Test Remediation Agent
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/remediation/health
```

### 2. Create a Workflow

```bash
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "template": "microservice-rest-api",
    "requested_by": "user@example.com",
    "parameters": {
      "service_name": "user-service",
      "language": "python",
      "database": "postgresql",
      "environment": "dev"
    }
  }'
```

### 3. Generate Microservice Code

```bash
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/generate \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "payment-service",
    "language": "python",
    "database": "postgresql",
    "api_type": "rest",
    "environment": "dev"
  }'
```

### 4. Check Workflow Status

```bash
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/workflows/wf-abc123
```

---

## Architecture Diagram

```
Internet
   │
   ▼
┌─────────────────────────────────────────┐
│   API Gateway (Public)                   │
│   https://d9bf4clz2f.execute-api...     │
│   - POST /workflows                      │
│   - POST /generate                       │
│   - POST /remediate                      │
│   - GET /*/health                        │
└──────────────┬──────────────────────────┘
               │
               │ VPC Link
               ▼
┌─────────────────────────────────────────┐
│   Application Load Balancer (Private)   │
│   - Port 80 HTTP                        │
│   - 3 Target Groups                     │
│   - Health checks configured            │
└──────────────┬──────────────────────────┘
               │
       ┌───────┼───────┐
       │       │       │
       ▼       ▼       ▼
   ┌──────┐ ┌──────┐ ┌──────┐
   │Planner CodeGen│ │Remed.│
   │:8000  │:8001  │ │:8002 │
   │(ECS)  │(ECS)  │ │(ECS) │
   └───┬───┘└───┬───┘└───┬──┘
       │        │        │
       └────────┼────────┘
                │
       ┌────────┼────────┐
       │        │        │
       ▼        ▼        ▼
   ┌────────┐ ┌────┐ ┌─────────┐
   │DynamoDB│ │ S3 │ │ Secrets │
   │        │ │    │ │ Manager │
   └────────┘ └────┘ └─────────┘
```

---

## Resource Count

| Category | Count |
|----------|-------|
| **Total AWS Resources** | 90+ |
| **ECS Services** | 3 |
| **ALB + Target Groups** | 1 + 3 |
| **API Gateway Routes** | 7 |
| **DynamoDB Tables** | 4 |
| **S3 Buckets** | 4 |
| **Secrets** | 3 |
| **VPC Components** | VPC + 6 subnets + 3 NAT Gateways |
| **Security Groups** | 4 |

---

## Monitoring & Logs

### View Logs

```bash
# All ECS container logs
aws logs tail /aws/ecs/dev-agentic-cluster --follow

# Planner Agent logs
aws logs tail /aws/ecs/dev-agentic-cluster --follow --filter-pattern planner

# API Gateway logs
aws logs tail /aws/apigateway/dev-agentic-api --follow
```

### Check Service Status

```bash
# List ECS services
aws ecs list-services \
  --cluster dev-agentic-cluster \
  --region us-east-1

# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn>
```

---

## Next Steps

### Immediate (Ready Now):
1. ✅ Test API Gateway endpoints
2. ✅ Create workflows via API
3. ✅ Generate microservices

### Short Term:
1. Configure GitLab credentials in Secrets Manager for repository creation
2. Add authentication to API Gateway (AWS IAM or JWT)
3. Set up custom domain for API Gateway
4. Configure CloudWatch alarms for service health

### Medium Term:
1. Deploy ArgoCD for GitOps workflows
2. Implement Policy Agent with OPA
3. Add Observability Agent with OpenTelemetry
4. Deploy Backstage developer portal

### Long Term:
1. Multi-environment setup (staging, production)
2. CI/CD pipeline for agent updates
3. Custom metrics and dashboards
4. Auto-scaling policies optimization

---

## Troubleshooting

### Issue: Can't reach API Gateway
**Check**:
```bash
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/planner/health
```
**Expected**: JSON response with `"status": "healthy"`

### Issue: Agents not responding
**Check ECS service health**:
```bash
aws ecs describe-services \
  --cluster dev-agentic-cluster \
  --services dev-planner-agent dev-codegen-agent dev-remediation-agent \
  --region us-east-1
```

### Issue: ALB health checks failing
**Check target health**:
```bash
# Get target group ARNs
aws elbv2 describe-target-groups \
  --names dev-planner-tg dev-codegen-tg dev-remediation-tg \
  --region us-east-1

# Check health status
aws elbv2 describe-target-health \
  --target-group-arn <arn-from-above>
```

---

## Cost Estimate (Monthly)

Based on current configuration:

| Service | Estimated Cost |
|---------|----------------|
| ECS Fargate (3 tasks, 24/7) | ~$35-45 |
| Application Load Balancer | ~$20-25 |
| API Gateway | ~$3-5 (first 1M requests free) |
| VPC (NAT Gateways) | ~$100-120 |
| DynamoDB (on-demand) | ~$5-10 |
| S3 Storage | ~$2-5 |
| CloudWatch Logs | ~$5-10 |
| Secrets Manager | ~$2 |
| **Total** | **~$170-220/month** |

---

## Security Notes

1. **Private Networking**: All agents run in private subnets with no direct internet access
2. **Load Balancer**: Internal ALB not exposed to internet
3. **VPC Link**: Secure connection between API Gateway and private resources
4. **Secrets**: API keys stored in Secrets Manager with encryption
5. **IAM Roles**: Minimal permissions for each service
6. **Security Groups**: Restrictive ingress/egress rules

---

## Files Changed in This Deployment

### New Files:
- `iac/terraform/modules/ecs/load_balancer.tf` - ALB configuration
- `docs/USAGE_GUIDE.md` - Complete usage documentation

### Modified Files:
- `iac/terraform/modules/ecs/task_definitions.tf` - Added ALB integration
- `iac/terraform/modules/ecs/outputs.tf` - Added ALB outputs
- `iac/terraform/modules/api_gateway/main.tf` - Added VPC Link and routes
- `iac/terraform/modules/api_gateway/variables.tf` - Added ALB variables
- `iac/terraform/modules/api_gateway/outputs.tf` - Uncommented VPC Link output
- `iac/terraform/modules/s3/main.tf` - Commented out duplicate state bucket
- `iac/terraform/main.tf` - Passed ALB config to API Gateway module

---

## Quick Reference

**API Gateway Base URL**:
`https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev`

**AWS Console Links**:
- [ECS Cluster](https://console.aws.amazon.com/ecs/home?region=us-east-1#/clusters/dev-agentic-cluster)
- [API Gateway](https://console.aws.amazon.com/apigateway/home?region=us-east-1#/apis/d9bf4clz2f)
- [Load Balancer](https://console.aws.amazon.com/ec2/home?region=us-east-1#LoadBalancers:)
- [CloudWatch Logs](https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups)

**Documentation**:
- [README.md](./README.md) - Project overview
- [architecture.md](./architecture.md) - Detailed architecture
- [USAGE_GUIDE.md](./docs/USAGE_GUIDE.md) - How to use the framework

---

**Status**: System is operational and ready for use! 🚀
