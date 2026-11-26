# Secrets (never in Git)

Created by hand on the EC2 host. Values are generated there and never printed.

## `registration/postgres-auth`

| Key | Used by | Content |
|---|---|---|
| `POSTGRES_PASSWORD` | Postgres StatefulSet (first init only) | random hex, 32 chars |
| `DATABASE_URL` | web Deployment | `postgresql://portal:<password>@postgres:5432/registration` |

Hex is URL-safe, so the password needs no escaping inside `DATABASE_URL`.

```bash
PGPASS=$(openssl rand -hex 16)
kubectl -n registration create secret generic postgres-auth --from-literal=POSTGRES_PASSWORD="$PGPASS" --from-literal=DATABASE_URL="postgresql://portal:$PGPASS@postgres:5432/registration"
unset PGPASS
```

Note: Postgres reads `POSTGRES_PASSWORD` only when it initialises an empty data directory.
Changing the Secret later does not change the database password.

## `registration/postgres-init` (ConfigMap, not secret — built from the app's SQL files)

```bash
kubectl -n registration create configmap postgres-init --from-file=app/schema.sql --from-file=app/seed.sql
```
