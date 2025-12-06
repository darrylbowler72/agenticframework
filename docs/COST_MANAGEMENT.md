# AWS Cost Management Guide

This guide helps you manage AWS costs for the Agentic Framework by tearing down and recreating infrastructure as needed.

## Overview

When not actively using the framework, you can destroy all infrastructure to avoid AWS costs. The infrastructure can be easily recreated when needed.

## Estimated Costs

### Running Infrastructure (24/7)
- **ECS Fargate Tasks (4 agents)**: ~$50-70/month
- **Application Load Balancer**: ~$16/month
- **API Gateway**: ~$3.50/1M requests
- **DynamoDB**: ~$5/month (on-demand pricing)
- **CloudWatch Logs**: ~$1-5/month
- **Secrets Manager**: ~$1/month
- **Data Transfer**: Variable
- **Total**: ~$75-100/month (continuous operation)

### After Destroy
- **S3 Storage (if not emptied)**: ~$0.023/GB/month
- **ECR Storage (if images retained)**: ~$0.10/GB/month
- **CloudWatch Logs (retention)**: ~$0.50/GB/month
- **Total**: ~$1-5/month (minimal storage costs)

## Quick Start

### Destroy Infrastructure

```bash
# Interactive destroy (recommended)
bash scripts/06-destroy-infrastructure.sh

# The script will:
# 1. Ask for confirmation
# 2. Optionally empty S3 buckets
# 3. Optionally delete ECR images
# 4. Optionally scale down ECS services first
# 5. Run terraform destroy
```

### Recreate Infrastructure

```bash
# Redeploy everything
bash scripts/03-deploy-infrastructure.sh
bash scripts/05-deploy-agents-podman.sh
```

## Destroy Process Explained

### Step 1: Confirmation
You'll be asked to confirm destruction twice:
1. Type "yes" to proceed
2. Type the environment name (e.g., "dev") to confirm

### Step 2: S3 Bucket Cleanup (Optional)
**Question**: "Empty S3 buckets? (yes/no)"

- **yes**: Deletes all objects in S3 buckets (except terraform-state)
- **no**: Keeps S3 contents (buckets cannot be destroyed if not empty)

**Recommendation**: Say **yes** unless you have important artifacts to preserve.

### Step 3: ECR Image Cleanup (Optional)
**Question**: "Delete ECR images? (yes/no)"

- **yes**: Deletes all container images from ECR repositories
- **no**: Keeps images (repositories preserved but can be destroyed)

**Recommendation**: Say **yes** - images can be rebuilt quickly (~5-10 minutes)

### Step 4: ECS Service Scale Down (Optional)
**Question**: "Scale ECS services to 0 before destroy? (yes/no)"

- **yes**: Scales services to 0 tasks before destroy (faster cleanup)
- **no**: Terraform handles service shutdown (may take longer)

**Recommendation**: Say **yes** for faster destruction.

### Step 5: Terraform Destroy
Terraform destroys all infrastructure:
- ECS Cluster and Services
- Application Load Balancer
- API Gateway
- VPC and Networking
- DynamoDB Tables
- EventBridge Event Bus
- IAM Roles and Policies
- CloudWatch Log Groups

### Step 6: Local State Cleanup (Optional)
**Question**: "Remove local state? (yes/no)"

- **yes**: Removes local terraform.tfstate files
- **no**: Keeps local state (useful for troubleshooting)

**Recommendation**: Say **yes** if destroy completed successfully.

## What Gets Destroyed

| Resource | Destroyed? | Cost After Destroy |
|----------|------------|-------------------|
| ECS Cluster & Services | ✅ Yes | $0 |
| Application Load Balancer | ✅ Yes | $0 |
| API Gateway | ✅ Yes | $0 |
| VPC & Networking | ✅ Yes | $0 |
| DynamoDB Tables | ✅ Yes | $0 |
| EventBridge Event Bus | ✅ Yes | $0 |
| IAM Roles/Policies | ✅ Yes | $0 |
| CloudWatch Logs | ✅ Yes | $0 |
| S3 Buckets (empty) | ✅ Yes | $0 |
| S3 Buckets (with content) | ❌ No | ~$0.023/GB/month |
| ECR Repositories | ❌ No | ~$0.10/GB/month |
| Terraform State Bucket | ❌ No | ~$0.023/GB (minimal) |

## What Gets Preserved

These resources are intentionally preserved:

1. **Terraform State Bucket** (`dev-agentic-terraform-state`)
   - Required to recreate infrastructure
   - Minimal cost (~$0.05/month)

2. **S3 Buckets with Content** (if you skip emptying)
   - Templates bucket
   - Artifacts bucket
   - Cost: ~$0.023/GB/month

3. **ECR Repositories** (if you skip image deletion)
   - Container images for agents
   - Cost: ~$0.10/GB/month

4. **GitHub Credentials in Secrets Manager**
   - Used by chatbot for GitHub operations
   - Cost: ~$0.40/month per secret

## Cost Optimization Strategies

### Strategy 1: Fully Destroy When Not In Use
**Best for**: Infrequent usage (once per week or less)

```bash
# Destroy everything
bash scripts/06-destroy-infrastructure.sh
# Answer "yes" to all optional cleanup steps

# Cost: ~$1-2/month (minimal storage)
# Rebuild time: ~15-20 minutes
```

### Strategy 2: Keep Images, Destroy Infrastructure
**Best for**: Regular usage (multiple times per week)

```bash
# Destroy but keep ECR images
bash scripts/06-destroy-infrastructure.sh
# Answer "no" to ECR image deletion
# Answer "yes" to everything else

# Cost: ~$3-5/month (ECR images + minimal storage)
# Rebuild time: ~5-10 minutes (no image rebuild)
```

### Strategy 3: Scale Down Without Destroying
**Best for**: Daily usage with overnight pauses

```bash
# Scale ECS services to 0 (keeps infrastructure)
aws ecs update-service --cluster dev-agentic-cluster \
  --service dev-planner-agent --desired-count 0 \
  --region us-east-1

# Repeat for other services

# Cost: ~$16/month (ALB + minimal)
# Restart time: ~2-3 minutes
```

### Strategy 4: Use Spot Instances (Future Enhancement)
ECS Fargate Spot can reduce costs by 50-70% but may experience interruptions.

## Rebuilding Infrastructure

### Full Rebuild (from scratch)
```bash
# If you destroyed everything including images
bash scripts/03-deploy-infrastructure.sh
bash scripts/05-deploy-agents-podman.sh

# Time: ~15-20 minutes
```

### Quick Rebuild (images preserved)
```bash
# If you kept ECR images
bash scripts/03-deploy-infrastructure.sh

# Images are already in ECR, so ECS pulls them automatically
# Time: ~5-10 minutes
```

## Troubleshooting Destroy Issues

### Issue: S3 Bucket Not Empty
```
Error: Cannot destroy S3 bucket - bucket not empty
```

**Solution**:
```bash
# Empty buckets manually
aws s3 rm s3://dev-agentic-artifacts --recursive
aws s3 rm s3://dev-agentic-templates --recursive

# Rerun destroy
bash scripts/06-destroy-infrastructure.sh
```

### Issue: ECR Repository Has Images
```
Error: Cannot delete repository with existing images
```

**Solution**:
```bash
# Delete images manually
for repo in planner-agent codegen-agent remediation-agent chatbot-agent; do
  aws ecr batch-delete-image \
    --repository-name dev-$repo \
    --image-ids "$(aws ecr list-images --repository-name dev-$repo --query 'imageIds[*]' --output json)"
done

# Rerun destroy
bash scripts/06-destroy-infrastructure.sh
```

### Issue: ECS Services Won't Terminate
```
Error: ECS services still have running tasks
```

**Solution**:
```bash
# Force stop all tasks
for service in dev-planner-agent dev-codegen-agent dev-remediation-agent dev-chatbot-agent; do
  aws ecs update-service --cluster dev-agentic-cluster \
    --service $service --desired-count 0 --region us-east-1
done

# Wait 60 seconds
sleep 60

# Rerun destroy
bash scripts/06-destroy-infrastructure.sh
```

### Issue: DynamoDB Tables Have Data
Terraform will destroy DynamoDB tables even with data. If you need to preserve data:

```bash
# Backup DynamoDB table
aws dynamodb scan --table-name dev-workflow-executions \
  --output json > workflow-backup.json

# Restore after rebuild
aws dynamodb batch-write-item --request-items file://workflow-backup.json
```

## Best Practices

1. **Always Run Destroy Script First**
   - Use `scripts/06-destroy-infrastructure.sh` instead of manual `terraform destroy`
   - The script handles cleanup properly

2. **Empty S3 Buckets**
   - Answer "yes" to S3 cleanup unless you need to preserve artifacts
   - Keeps costs minimal

3. **Delete ECR Images**
   - Answer "yes" unless you rebuild frequently
   - Images rebuild in ~5 minutes

4. **Keep Terraform State Bucket**
   - Never delete `dev-agentic-terraform-state`
   - Required for infrastructure recreation

5. **Monitor Costs**
   ```bash
   # Check current AWS costs
   aws ce get-cost-and-usage \
     --time-period Start=2025-12-01,End=2025-12-05 \
     --granularity MONTHLY \
     --metrics BlendedCost
   ```

6. **Set Budget Alerts**
   - Create AWS Budget alerts for unexpected costs
   - Recommended: Alert at $50 and $100

## FAQ

**Q: How long does destroy take?**
A: 5-10 minutes total with all optional cleanup steps.

**Q: Can I destroy just the ECS services?**
A: No, use scale-to-zero instead (Strategy 3 above).

**Q: Will I lose my data?**
A: Yes, DynamoDB tables are destroyed. Backup first if needed.

**Q: Can I destroy just one agent?**
A: Not easily. Terraform manages everything as a unit.

**Q: What if destroy fails?**
A: Check troubleshooting section above, fix issues, rerun script.

**Q: How much will I save?**
A: From ~$75-100/month to ~$1-5/month (~95% reduction).

**Q: How do I prevent accidental destroy?**
A: Script requires double confirmation and environment name.

## Cost Monitoring Commands

```bash
# Check current ECS costs
aws ce get-cost-and-usage \
  --time-period Start=2025-12-01,End=2025-12-05 \
  --granularity DAILY \
  --metrics BlendedCost \
  --group-by Type=SERVICE \
  --filter file://filter.json

# Check running ECS tasks
aws ecs list-tasks --cluster dev-agentic-cluster

# Check ALB status
aws elbv2 describe-load-balancers \
  --names internal-dev-agents-alb

# Check DynamoDB table sizes
aws dynamodb describe-table \
  --table-name dev-workflow-executions \
  --query 'Table.TableSizeBytes'
```

## Summary

To minimize AWS costs when not using the framework:

1. Run: `bash scripts/06-destroy-infrastructure.sh`
2. Answer "yes" to all cleanup options
3. Cost drops to ~$1-5/month
4. Rebuild anytime with deployment scripts
5. Total rebuild time: 15-20 minutes

For questions or issues, check the troubleshooting section or create a GitHub issue.
