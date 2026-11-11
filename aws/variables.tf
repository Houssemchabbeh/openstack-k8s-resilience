variable "region" {
  description = "Learner Lab region"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "Must be an 8th-gen Intel type (C8i/M8i/R8i) for nested virtualization; Learner Lab allows up to *.large"
  type        = string
  default     = "r8i.large"
}

variable "root_volume_gb" {
  description = "Root disk size. DevStack + Cinder LVM + Swift + VM disks + Jenkins need ~80 GB"
  type        = number
  default     = 80
}

variable "public_key_path" {
  description = "Public half of the SSH key generated locally (private key never leaves the laptop)"
  type        = string
  default     = "~/.ssh/devstack.pub"
}

variable "ssh_cidr" {
  description = "Who may reach port 22. Key-only login; tighten to <your-ip>/32 if wanted"
  type        = string
  default     = "0.0.0.0/0"
}
