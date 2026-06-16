---
applyTo: ".github/workflows/**"
description: "Use when working on Markly Azure operations, App Service deployment, Docker images, production SQLite database pull/push workflows, Kudu, ACR, or production restarts."
---

# Azure Operations & Connection Guide

How any agent can connect to Azure to inspect, pull, or deploy the production Markly app.

## Resource Facts
| Thing | Value |
| --- | --- |
| App Service name | `markly` |
| Resource group | `markly-rg` |
| Public host | `https://markly.azurewebsites.net` |
| SCM (Kudu) host | `https://markly.scm.azurewebsites.net` |
| Container registry | `marklyregistry.azurecr.io` (image: `markly:latest`) |
| Prod DB path (in container) | `/home/data/markly.db` (SQLite) |
| Local DB path | `backend/markly.db` |

## Prerequisites
- Azure CLI installed (`az`) and logged in: run `az login` once if needed.
- Verify access: `az webapp list --query "[].{name:name,rg:resourceGroup,host:defaultHostName}" -o table`

## Get an access token (used by all SCM/Kudu calls)
```bash
TOKEN=$(az account get-access-token --query accessToken --output tsv)
```

## Pull the production database to local
The prod DB is a SQLite file served over the Kudu VFS API.
```bash
TOKEN=$(az account get-access-token --query accessToken --output tsv)

# Download prod DB to a temp file
curl -sS -H "Authorization: Bearer $TOKEN" \
  "https://markly.scm.azurewebsites.net/api/vfs/data/markly.db" \
  -o /tmp/markly_prod.db

# Validate before replacing
sqlite3 /tmp/markly_prod.db "PRAGMA integrity_check; SELECT count(*) FROM bookmarks;"

# Back up local, clear stale WAL/SHM, then swap in the prod copy
cd backend
cp markly.db "markly.db.bak.$(date +%Y%m%d_%H%M%S)"
rm -f markly.db-wal markly.db-shm
cp /tmp/markly_prod.db markly.db
```

## Push a database back to production
```bash
TOKEN=$(az account get-access-token --query accessToken --output tsv)
curl -sS -X PUT -H "Authorization: Bearer $TOKEN" \
  --data-binary @backend/markly.db \
  "https://markly.scm.azurewebsites.net/api/vfs/data/markly.db"
# Then restart the App Service (see below).
```
**Ask first** before writing to the prod DB - it is the live datastore.

## Deploy a new build
On Apple Silicon you **must** build for `linux/amd64`.
```bash
docker login marklyregistry.azurecr.io -u marklyregistry   # password from Azure Portal > ACR > Access Keys
docker build --platform linux/amd64 -t marklyregistry.azurecr.io/markly:latest . \
  && docker push marklyregistry.azurecr.io/markly:latest
az webapp restart --name markly --resource-group markly-rg
```

## Useful operations
```bash
# Restart the app
az webapp restart --name markly --resource-group markly-rg

# Tail live logs
az webapp log tail --name markly --resource-group markly-rg

# Open an SSH session into the container
az webapp ssh --name markly --resource-group markly-rg

# List / read files in the persistent data dir via Kudu VFS
curl -sS -H "Authorization: Bearer $TOKEN" \
  "https://markly.scm.azurewebsites.net/api/vfs/data/"
```

## Diagnosing a production 500 / reading tracebacks
App logs (including Python tracebacks) land in dated files under `LogFiles`,
served over the Kudu VFS API. `az webapp log tail` only shows the live stream;
to inspect a past error, read the saved files directly.
```bash
TOKEN=$(az account get-access-token --query accessToken --output tsv)

# 1. List available log files and find the latest *containerStream* one
curl -sS -H "Authorization: Bearer $TOKEN" \
  "https://markly.scm.azurewebsites.net/api/vfs/LogFiles/"

# 2. Fetch a specific log (filenames are dated, e.g. YYYY_MM_DD_<host>_containerStream.log).
#    Logs may contain NUL bytes, so strip them, then grep for the failure.
curl -sS -H "Authorization: Bearer $TOKEN" \
  "https://markly.scm.azurewebsites.net/api/vfs/LogFiles/<filename>.log" \
  | tr -d '\000' \
  | grep -iaE "Traceback|Error|Exception|sqlite3" | tail -60
```
Tip: a `sqlite3.OperationalError: database is locked` is write-lock contention
(DELETE journal mode serializes writers), usually transient — the connection
`busy_timeout` controls how long a writer waits before giving up.

## Guardrails
- Never commit secrets, tokens, or `.env` files. `.env` holds live API keys.
- Ask first before writing to prod (DB upload, deploy, restart).
- Always validate a pulled DB with `PRAGMA integrity_check` before using it.
