# openstack-k8s-resilience

A course-registration portal running on Kubernetes (k3s), on a private
OpenStack cloud (DevStack), hosted on a single AWS EC2 machine built with
Terraform. The platform is then broken on purpose, and each failure is
measured for downtime, data lost and correctness.

> **Status: in progress.** The host, the OpenStack cloud, the k3s cluster and
> the application are built. Storage, backups, delivery and the failure drills
> are the next milestones. See [Status](#status) for the exact split.

## Why this project

Most demos show a platform working. This one is about what happens when it
stops working: a pod is killed, a VM is deleted, a table is dropped, the host
is restarted. The application was chosen so that mistakes are visible. A
course has a fixed number of seats, so after any failure two questions have a
yes or no answer:

- Was a seat sold twice (overbooking)?
- Was a student registered twice (duplicates)?

## Architecture

![Architecture: a developer laptop reaches, through an SSH tunnel, the floating IP of a k3s cluster (node-a server, node-b agent) running inside OpenStack DevStack on one AWS EC2 instance. Traefik routes to two web pods and a PostgreSQL StatefulSet on a Cinder volume; a CronJob sends pg_dump backups to Swift; Jenkins on the host delivers images via GHCR. The animation steps through the request path, delivery, backups and failure drills.](docs/diagrams/architecture.gif)

Everything runs inside one EC2 instance. Nested virtualization lets the
OpenStack VMs use KVM instead of slow emulation. Only SSH is open on the
instance; Horizon, the portal and Jenkins are reached through SSH tunnels.

| Layer | What it is | Where it lives in this repo |
|---|---|---|
| Host | EC2 `r8i.large`, Ubuntu 26.04, 80 GB gp3, IMDSv2 only | [`aws/`](aws/) |
| Private cloud | DevStack with Swift and Cinder backup enabled | [`devstack/local.conf.example`](devstack/local.conf.example) |
| Nodes | Two OpenStack VMs, same first-boot config | [`cloud-init/node.yaml`](cloud-init/node.yaml) |
| Cluster | k3s: `node-a` server, `node-b` agent, flannel VXLAN | installed by hand (milestone M2) |
| Application | Flask portal on gunicorn, PostgreSQL | [`app/`](app/) |

## The application

A small Flask portal where a student picks a course and gets a receipt.

**The one transaction the project protects** is in
[`app/portal/registration.py`](app/portal/registration.py):

1. Lock the course row (`SELECT ... FOR UPDATE`), so two registrations for the
   same course cannot read the seat count at the same time.
2. If the student is already registered, return the same receipt. A retry
   after a timeout is therefore safe.
3. If the course is full, write nothing.
4. Insert the registration and take the seat in the same transaction.

The database enforces the same rules a second time: `seats_taken` can never
exceed `capacity` (CHECK constraint) and a student can register for a course
only once (UNIQUE constraint).

**When the database is down**, every route answers `503` with a `Retry-After`
header and a maintenance page that shows the last known course list, instead
of an error page.

**Correctness check.** [`app/portal/checks.py`](app/portal/checks.py) verifies,
in one database snapshot, that there is no overbooking, no duplicate
registration and that seat counters match the real number of registrations.
It is exposed on an admin route and is meant to run after every drill.

Routes: course list, register, receipt, `healthz`, `readyz`, admin check.

## Run the application tests

The tests need a PostgreSQL database.

```bash
cd app
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

20 tests cover the registration rules (including a race for the last seats and
a double submit), the HTTP behaviour and the maintenance mode.

## Deploy the host

```bash
cd aws
terraform init
terraform apply
terraform output ssh_config    # paste into ~/.ssh/config
```

Requirements: an AWS account that allows 8th-generation Intel instance types
(needed for nested virtualization) and a local SSH key at `~/.ssh/devstack`.

DevStack is then installed on the host from
[`devstack/local.conf.example`](devstack/local.conf.example) (fill in the
placeholders on the host, never in Git) with `./stack.sh`. Tested on
2026-11-11 with DevStack master on Ubuntu 26.04; the install took 783 seconds.

## Status

**Built**

- **M0, host and cloud:** EC2 host with Terraform, DevStack running, a
  dedicated `resilience` project and user in Keystone.
- **M1, network and nodes:** private network, router, floating IP, security
  group, two VMs configured by cloud-init.
- **M2, cluster:** k3s server and agent, flannel with the MTU lowered for the
  nested VXLAN.
- **M3a, application:** portal, schema, registration transaction, maintenance
  mode, correctness check, container image, tests.

Evidence for each milestone is in [`docs/screenshots/`](docs/screenshots/).

**Planned**

- Deploy the portal on the cluster (manifests, Traefik ingress).
- PostgreSQL on a Cinder volume through the Cinder CSI driver.
- Backups with `pg_dump` to Swift every 15 minutes, restore-tested nightly.
- Jenkins delivery: build with Podman, push to GHCR, rolling update with
  automatic rollback.
- The failure drills, each measured for downtime, data lost (RPO) and
  correctness: pod kill, VM delete, table drop, host restart.

No drill results are published yet because no drill has been run.

## Known limitations

- **One host.** The whole cloud lives on a single EC2 instance, so a host
  failure takes everything down. The host-restart drill measures recovery, not
  availability.
- **DevStack is a development distribution** of OpenStack, not a production
  deployment.
- **Manual steps.** DevStack and k3s are installed by hand; only the host and
  the node first-boot configuration are code.
- **SSH is open to any address by default** (`ssh_cidr`), with key-only login.
  Tighten it to your own IP if you reuse this.
- **The public DNS name changes** after every stop and start of the instance.

## Tech stack

AWS EC2 · Terraform · OpenStack (DevStack: Keystone, Nova, Glance, Neutron,
Cinder, Swift) · Kubernetes (k3s) · cloud-init · Python (Flask, psycopg,
gunicorn) · PostgreSQL · pytest
