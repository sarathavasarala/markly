# Deployment Guide

This project is containerized using Docker and can be deployed to any major cloud provider (Azure, AWS, Google Cloud).

## Prerequisites
- [Docker](https://www.docker.com/) installed and running.
- Access to a Container Registry (e.g., Azure ACR, Docker Hub).
- A host for the container (e.g., Azure App Service, AWS App Runner).

## 1. Local Development
Ensure your environment variables are set in `backend/.env` and `frontend/.env`.

```bash
# Start backend and frontend simultaneously
npm start
```

## 2. Build and Push (Production)

Substitute `<your-registry-url>` and `<image-name>` with your specific infrastructure details.

### Step 1: Login to your Registry
```bash
docker login <your-registry-url> -u <username>
```

### Step 2: Build for Production
*Crucial: If building on Apple Silicon (M1/M2/M3), use the `--platform linux/amd64` flag for compatibility with cloud servers.*

```bash
docker build --platform linux/amd64 -t <your-registry-url>/<image-name>:latest .
```

### Step 3: Push to Registry
```bash
docker push <your-registry-url>/<image-name>:latest
```

## 3. Server Configuration
- Ensure your cloud provider has all environment variables defined in its configuration panel.
- Set the container port (mapped in the Dockerfile) correctly in the host settings.
- Trigger a restart/pull from the registry to apply changes.

### Azure App Service SQLite configuration

The production database is a SQLite file owned by the Flask backend. In the Azure Portal:

1. Go to your App Service -> **Configuration** -> **General settings**.
2. Ensure `WEBSITES_ENABLE_APP_SERVICE_STORAGE` is enabled / set to `true`.
3. Go to **Configuration** -> **Application settings** and add:
   - `MARKLY_DB_PATH=/home/data/markly.db`
   - `FLASK_SECRET_KEY=<strong random secret>`
   - `ALLOWED_EMAILS=<your email>,<other allowed emails>`
   - `ENABLE_EMBEDDINGS=true`
   - `ENABLE_SEMANTIC_SEARCH=false`
   - `GOOGLE_CLIENT_ID=<google oauth client id>`
   - `GOOGLE_CLIENT_SECRET=<google oauth client secret>`
   - `OAUTH_REDIRECT_BASE_URL=https://<your-app>.azurewebsites.net`
   - your existing Azure OpenAI settings
4. In your Google OAuth client, add this redirect URI:
   - `https://<your-app>.azurewebsites.net/api/auth/google/callback`
5. In App Service -> **SSH**, create the persistent folder once if needed:
   ```bash
   mkdir -p /home/data
   ```

Back up `/home/data/markly.db` periodically. A manual download is enough for small personal use; a later scheduled copy to Azure Blob Storage is safer.
