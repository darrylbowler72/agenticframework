# S3 Buckets Module

# Agent Artifacts Bucket
resource "aws_s3_bucket" "artifacts" {
  bucket = "${var.environment}-agent-artifacts-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.environment}-agent-artifacts"
  }
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Code Generation Templates Bucket
resource "aws_s3_bucket" "templates" {
  bucket = "${var.environment}-codegen-templates-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.environment}-codegen-templates"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "templates" {
  bucket = aws_s3_bucket.templates.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "templates" {
  bucket = aws_s3_bucket.templates.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Policy Bundles Bucket
resource "aws_s3_bucket" "policy_bundles" {
  bucket = "${var.environment}-policy-bundles-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.environment}-policy-bundles"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "policy_bundles" {
  bucket = aws_s3_bucket.policy_bundles.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "policy_bundles" {
  bucket = aws_s3_bucket.policy_bundles.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Terraform State Bucket - Already created by setup script, commented out to avoid conflict
# resource "aws_s3_bucket" "terraform_state" {
#   bucket = "${var.environment}-terraform-state-${data.aws_caller_identity.current.account_id}"
#
#   tags = {
#     Name = "${var.environment}-terraform-state"
#   }
# }
#
# resource "aws_s3_bucket_versioning" "terraform_state" {
#   bucket = aws_s3_bucket.terraform_state.id
#
#   versioning_configuration {
#     status = "Enabled"
#   }
# }
#
# resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
#   bucket = aws_s3_bucket.terraform_state.id
#
#   rule {
#     apply_server_side_encryption_by_default {
#       sse_algorithm = "AES256"
#     }
#   }
# }

data "aws_caller_identity" "current" {}

# Outputs
output "artifacts_bucket_name" {
  value = aws_s3_bucket.artifacts.id
}

output "templates_bucket_name" {
  value = aws_s3_bucket.templates.id
}

output "policy_bundles_bucket_name" {
  value = aws_s3_bucket.policy_bundles.id
}

# Commented out since terraform state bucket is managed externally
# output "terraform_state_bucket_name" {
#   value = aws_s3_bucket.terraform_state.id
# }
