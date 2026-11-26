# Jenkins (on the EC2 host, port 8090)

| Job | File | Trigger |
|---|---|---|
| `app-delivery` | [`app-delivery.Jenkinsfile`](app-delivery.Jenkinsfile) | polls GitHub every 5 min |
| `backup-verify` | [`backup-verify.Jenkinsfile`](backup-verify.Jenkinsfile) | nightly |

Both: *Pipeline script from SCM* → Git → this repo, branch `main`, script path `jenkins/<file>`.

## Host prerequisites (user `jenkins`)
- Jenkins LTS on port **8090** (8080 = Swift proxy), Java 21.
- `podman` (rootless for `jenkins`: entries in `/etc/subuid` and `/etc/subgid`), `kubectl`, `openstack` CLI, `curl`, `git` on the `PATH` of the `jenkins` user.
- Plugins: Pipeline, Git, Credentials Binding, JUnit (suggested plugins cover them).

## Credentials (Manage Jenkins → Credentials, never in Git)

| ID | Kind | Content |
|---|---|---|
| `ghcr-push` | Username with password | GitHub user + classic PAT (`write:packages`) |
| `k3s-kubeconfig` | Secret file | kubeconfig with `server: https://172.24.4.73:6443` (node-a floating IP, in the k3s `--tls-san`) |
| `openstack-clouds-yaml` | Secret file | `clouds.yaml` with **only** the `resilience-appcred` cloud |
