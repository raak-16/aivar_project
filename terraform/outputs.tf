output "dynamodb_table_name" {
  value = aws_dynamodb_table.actions.name
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.runtime.name
}
