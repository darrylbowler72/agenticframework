#!/bin/bash
# Manual AWS Infrastructure Teardown Script
# Use this when Terraform state is out of sync

set -e

REGION="us-east-1"
CLUSTER="dev-agentic-cluster"

echo "========================================="
echo "AWS Infrastructure Manual Teardown"
echo "========================================="
echo ""
echo "This will destroy all AWS resources for the dev environment"
echo "Region: $REGION"
echo "Cluster: $CLUSTER"
echo ""

# Step 1: Delete ECS Services
echo "Step 1: Deleting ECS Services..."
SERVICES=$(aws ecs list-services --cluster $CLUSTER --region $REGION --query 'serviceArns[]' --output text)

for service in $SERVICES; do
    SERVICE_NAME=$(basename $service)
    echo "  - Scaling down and deleting service: $SERVICE_NAME"

    # Scale down to 0
    aws ecs update-service \
        --cluster $CLUSTER \
        --service $SERVICE_NAME \
        --desired-count 0 \
        --region $REGION \
        --query 'service.serviceName' \
        --output text || echo "    Failed to scale down $SERVICE_NAME"

    # Delete service
    aws ecs delete-service \
        --cluster $CLUSTER \
        --service $SERVICE_NAME \
        --force \
        --region $REGION \
        --query 'service.serviceName' \
        --output text || echo "    Failed to delete $SERVICE_NAME"
done

echo "  Waiting 30 seconds for services to drain..."
sleep 30

# Step 2: Stop all running tasks
echo ""
echo "Step 2: Stopping all running tasks..."
TASKS=$(aws ecs list-tasks --cluster $CLUSTER --region $REGION --query 'taskArns[]' --output text)

for task in $TASKS; do
    echo "  - Stopping task: $(basename $task)"
    aws ecs stop-task \
        --cluster $CLUSTER \
        --task $(basename $task) \
        --region $REGION \
        --query 'task.taskArn' \
        --output text || echo "    Failed to stop task"
done

# Step 3: Delete ECS Cluster
echo ""
echo "Step 3: Deleting ECS Cluster..."
aws ecs delete-cluster \
    --cluster $CLUSTER \
    --region $REGION \
    --query 'cluster.clusterName' \
    --output text || echo "  Failed to delete cluster"

# Step 4: Delete Application Load Balancer
echo ""
echo "Step 4: Deleting Application Load Balancer..."
ALB_ARN=$(aws elbv2 describe-load-balancers \
    --region $REGION \
    --query 'LoadBalancers[?starts_with(LoadBalancerName, `dev-agents`)].LoadBalancerArn' \
    --output text)

if [ ! -z "$ALB_ARN" ]; then
    echo "  - Found ALB: $ALB_ARN"

    # Delete listeners first
    LISTENERS=$(aws elbv2 describe-listeners \
        --load-balancer-arn $ALB_ARN \
        --region $REGION \
        --query 'Listeners[].ListenerArn' \
        --output text)

    for listener in $LISTENERS; do
        echo "    - Deleting listener: $(basename $listener)"
        aws elbv2 delete-listener \
            --listener-arn $listener \
            --region $REGION || echo "      Failed to delete listener"
    done

    # Delete ALB
    aws elbv2 delete-load-balancer \
        --load-balancer-arn $ALB_ARN \
        --region $REGION || echo "  Failed to delete ALB"

    echo "  Waiting 30 seconds for ALB to delete..."
    sleep 30
else
    echo "  No ALB found"
fi

# Step 5: Delete Target Groups
echo ""
echo "Step 5: Deleting Target Groups..."
TARGET_GROUPS=$(aws elbv2 describe-target-groups \
    --region $REGION \
    --query 'TargetGroups[?starts_with(TargetGroupName, `dev-`)].TargetGroupArn' \
    --output text)

for tg in $TARGET_GROUPS; do
    echo "  - Deleting target group: $(basename $tg)"
    aws elbv2 delete-target-group \
        --target-group-arn $tg \
        --region $REGION || echo "    Failed to delete target group"
done

# Step 6: Delete API Gateway
echo ""
echo "Step 6: Deleting API Gateway..."
API_ID=$(aws apigatewayv2 get-apis \
    --region $REGION \
    --query 'Items[?Name==`dev-agentic-api`].ApiId' \
    --output text)

if [ ! -z "$API_ID" ]; then
    echo "  - Deleting API Gateway: $API_ID"
    aws apigatewayv2 delete-api \
        --api-id $API_ID \
        --region $REGION || echo "  Failed to delete API Gateway"
else
    echo "  No API Gateway found"
fi

# Step 7: Delete DynamoDB Tables
echo ""
echo "Step 7: Deleting DynamoDB Tables..."
for table in "dev-workflows" "dev-chatbot-sessions"; do
    echo "  - Deleting table: $table"
    aws dynamodb delete-table \
        --table-name $table \
        --region $REGION \
        --query 'TableDescription.TableName' \
        --output text 2>/dev/null || echo "    Table $table not found or already deleted"
done

# Step 8: List remaining resources (VPC, Security Groups, etc.)
echo ""
echo "Step 8: Listing remaining resources (manual cleanup may be needed)..."
echo ""
echo "VPCs with 'dev' or 'agentic' in tags:"
aws ec2 describe-vpcs \
    --region $REGION \
    --filters "Name=tag:Name,Values=*dev*,*agentic*" \
    --query 'Vpcs[].[VpcId,Tags[?Key==`Name`].Value|[0]]' \
    --output table || echo "  No VPCs found"

echo ""
echo "Security Groups with 'dev' or 'agentic' in name:"
aws ec2 describe-security-groups \
    --region $REGION \
    --filters "Name=group-name,Values=*dev*,*agentic*" \
    --query 'SecurityGroups[].[GroupId,GroupName]' \
    --output table || echo "  No Security Groups found"

echo ""
echo "S3 Buckets with 'agentic' or 'terraform' in name:"
aws s3 ls | grep -E "agentic|terraform" || echo "  No matching S3 buckets found"

echo ""
echo "========================================="
echo "Manual Teardown Complete!"
echo "========================================="
echo ""
echo "NOTE: The following resources may still exist and require manual deletion:"
echo "  - VPC and networking components (subnets, route tables, internet gateways)"
echo "  - Security Groups"
echo "  - S3 Buckets (must be emptied first)"
echo "  - ECR Repositories and container images"
echo "  - CloudWatch Log Groups"
echo "  - Secrets Manager secrets"
echo "  - NAT Gateways and Elastic IPs"
echo ""
echo "To delete VPC resources, identify the VPC ID above and run:"
echo "  aws ec2 delete-vpc --vpc-id <VPC_ID> --region $REGION"
echo ""
echo "To delete S3 buckets, empty them first then run:"
echo "  aws s3 rb s3://<BUCKET_NAME> --force --region $REGION"
echo ""
