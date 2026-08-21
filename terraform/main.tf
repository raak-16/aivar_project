terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_dynamodb_table" "actions" {
  name         = "graduated-autonomy-actions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "action_id"

  attribute {
    name = "action_id"
    type = "S"
  }
}

resource "aws_cloudwatch_log_group" "runtime" {
  name              = "/aws/lambda/graduated-autonomy"
  retention_in_days = 14
}
