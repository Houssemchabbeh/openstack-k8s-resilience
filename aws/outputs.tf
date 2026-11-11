output "instance_id" {
  value = aws_instance.devstack.id
}

output "public_dns" {
  description = "Changes after every stop/start: run `terraform apply -refresh-only` then read it again"
  value       = aws_instance.devstack.public_dns
}

output "ssh_config" {
  description = "Paste into ~/.ssh/config on Windows"
  value       = <<-EOT
    Host devstack
      HostName ${aws_instance.devstack.public_dns}
      User ubuntu
      IdentityFile ~/.ssh/devstack
      ServerAliveInterval 60
  EOT
}
