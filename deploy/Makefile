# Makefile for VM Deployment
# Usage: make <target>

.PHONY: help init plan apply destroy ssh health ansible

TERRAFORM_DIR = terraform
ANSIBLE_DIR = ansible
KEY_NAME ?= axon-worker
KEY_PATH ?= ~/.ssh/$(KEY_NAME).pem

help:
	@echo "Axon Browser Worker - VM Deployment"
	@echo ""
	@echo "Usage:"
	@echo "  make init      - Initialize Terraform"
	@echo "  make plan      - Preview changes"
	@echo "  make apply     - Deploy VM(s)"
	@echo "  make destroy   - Destroy all resources"
	@echo "  make ssh       - SSH to first worker"
	@echo "  make health    - Check worker health"
	@echo "  make ansible   - Run Ansible playbook"
	@echo ""
	@echo "Prerequisites:"
	@echo "  1. aws configure (set up AWS credentials)"
	@echo "  2. cp terraform/terraform.tfvars.example terraform/terraform.tfvars"
	@echo "  3. Edit terraform/terraform.tfvars with your settings"

init:
	cd $(TERRAFORM_DIR) && terraform init

plan:
	cd $(TERRAFORM_DIR) && terraform plan

apply:
	cd $(TERRAFORM_DIR) && terraform apply

destroy:
	cd $(TERRAFORM_DIR) && terraform destroy

output:
	cd $(TERRAFORM_DIR) && terraform output

# SSH to first worker
ssh:
	@IP=$$(cd $(TERRAFORM_DIR) && terraform output -json worker_public_ips | jq -r '.[0]'); \
	echo "Connecting to $$IP..."; \
	ssh -i $(KEY_PATH) ubuntu@$$IP

# Check health of all workers
health:
	@for IP in $$(cd $(TERRAFORM_DIR) && terraform output -json worker_public_ips | jq -r '.[]'); do \
		echo "Checking $$IP..."; \
		curl -s http://$$IP:8080/health | jq . || echo "Failed to connect"; \
		echo ""; \
	done

# Generate Ansible inventory from Terraform output
inventory:
	@cd $(TERRAFORM_DIR) && terraform output -raw ansible_inventory > ../$(ANSIBLE_DIR)/inventory.ini
	@echo "Generated $(ANSIBLE_DIR)/inventory.ini"

# Run Ansible playbook
ansible: inventory
	cd $(ANSIBLE_DIR) && ansible-playbook -i inventory.ini deploy.yml

# Run Ansible with specific tags
ansible-code:
	cd $(ANSIBLE_DIR) && ansible-playbook -i inventory.ini deploy.yml --tags code

ansible-config:
	cd $(ANSIBLE_DIR) && ansible-playbook -i inventory.ini deploy.yml --tags config

ansible-restart:
	cd $(ANSIBLE_DIR) && ansible-playbook -i inventory.ini deploy.yml --tags restart

# VNC to first worker
vnc:
	@IP=$$(cd $(TERRAFORM_DIR) && terraform output -json worker_public_ips | jq -r '.[0]'); \
	echo "Opening VNC to $$IP:5900..."; \
	open vnc://$$IP:5900 || echo "Run: vncviewer $$IP:5900"

# Show all worker IPs
ips:
	@cd $(TERRAFORM_DIR) && terraform output -json worker_public_ips | jq -r '.[]'

# Show API URLs
urls:
	@cd $(TERRAFORM_DIR) && terraform output -json worker_api_urls | jq -r '.[]'
