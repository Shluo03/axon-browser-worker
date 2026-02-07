# AWS EC2 Deployment for Axon Browser Worker
#
# Usage:
#   1. Configure AWS credentials: aws configure
#   2. Initialize: terraform init
#   3. Plan: terraform plan
#   4. Deploy: terraform apply
#   5. Destroy: terraform destroy

terraform {
  required_version = ">= 1.0"

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

# Variables
variable "aws_region" {
  description = "AWS region to deploy"
  type        = string
  default     = "ap-northeast-1"  # Tokyo - good for Asia
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.xlarge"  # 4 vCPU, 16GB RAM - good for AdsPower
}

variable "instance_count" {
  description = "Number of worker instances"
  type        = number
  default     = 1
}

variable "key_name" {
  description = "SSH key pair name (must exist in AWS)"
  type        = string
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed for SSH access"
  type        = string
  default     = "0.0.0.0/0"  # Change to your IP for security
}

variable "project_name" {
  description = "Project name for resource tagging"
  type        = string
  default     = "axon-worker"
}

# Data sources
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Security Group
resource "aws_security_group" "worker" {
  name        = "${var.project_name}-sg"
  description = "Security group for Axon Browser Worker"
  vpc_id      = data.aws_vpc.default.id

  # SSH
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # Browser Worker API
  ingress {
    description = "Browser Worker API"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # VNC (for debugging)
  ingress {
    description = "VNC"
    from_port   = 5900
    to_port     = 5900
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  # WebRTC (future)
  ingress {
    description = "WebRTC"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # All outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "${var.project_name}-sg"
    Project = var.project_name
  }
}

# EC2 Instance
resource "aws_instance" "worker" {
  count = var.instance_count

  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_name
  vpc_security_group_ids = [aws_security_group.worker.id]
  subnet_id              = data.aws_subnets.default.ids[0]

  root_block_device {
    volume_size           = 80
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = file("${path.module}/cloud-init.yaml")

  tags = {
    Name    = "${var.project_name}-${count.index + 1}"
    Project = var.project_name
    Role    = "browser-worker"
  }
}

# Elastic IP (optional, for stable IP)
resource "aws_eip" "worker" {
  count    = var.instance_count
  instance = aws_instance.worker[count.index].id
  domain   = "vpc"

  tags = {
    Name    = "${var.project_name}-eip-${count.index + 1}"
    Project = var.project_name
  }
}

# Outputs
output "worker_public_ips" {
  description = "Public IPs of worker instances"
  value       = aws_eip.worker[*].public_ip
}

output "worker_private_ips" {
  description = "Private IPs of worker instances"
  value       = aws_instance.worker[*].private_ip
}

output "ssh_commands" {
  description = "SSH commands to connect"
  value = [
    for i, eip in aws_eip.worker :
    "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${eip.public_ip}"
  ]
}

output "worker_api_urls" {
  description = "Browser Worker API URLs"
  value = [
    for eip in aws_eip.worker :
    "http://${eip.public_ip}:8080"
  ]
}

output "ansible_inventory" {
  description = "Copy this to ansible/inventory.ini"
  value = <<-EOT
[workers]
%{for i, eip in aws_eip.worker~}
worker${i + 1} ansible_host=${eip.public_ip} ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/${var.key_name}.pem
%{endfor~}
EOT
}
