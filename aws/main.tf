# EC2 host that runs DevStack. DevStack itself is installed by hand (see docs).

# Latest official Ubuntu 26.04 LTS image (Canonical's AWS account)
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-resolute-26.04-amd64-server-*"]
  }
}

# Learner Lab gives us a default VPC; we use it instead of building one
data "aws_vpc" "default" {
  default = true
}

resource "aws_key_pair" "devstack" {
  key_name   = "devstack"
  public_key = file(pathexpand(var.public_key_path))
}

# Only SSH is open. Horizon, the portal and Jenkins are reached through SSH tunnels.
resource "aws_security_group" "devstack" {
  name        = "devstack-sg"
  description = "SSH only; everything else via SSH tunnels"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_cidr]
  }

  egress {
    description = "All outbound (apt, git, GHCR)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "devstack" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = aws_key_pair.devstack.key_name
  vpc_security_group_ids = [aws_security_group.devstack.id]

  # Lets the OpenStack VMs (node-a, node-b) run with KVM instead of slow emulation
  cpu_options {
    nested_virtualization = "enabled"
  }

  root_block_device {
    volume_size = var.root_volume_gb
    volume_type = "gp3"
  }

  # IMDSv2 only (token required)
  metadata_options {
    http_tokens = "required"
  }

  tags = {
    Name = "devstack"
  }

  # A newer Ubuntu AMI must not trigger a replacement (that would wipe DevStack)
  lifecycle {
    ignore_changes = [ami]
  }
}
