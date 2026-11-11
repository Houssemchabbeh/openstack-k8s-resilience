terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source = "hashicorp/aws"
      # cpu_options.nested_virtualization needs a recent 6.x provider
      version = ">= 6.70, < 7.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project = "openstack-k8s-resilience"
    }
  }
}
