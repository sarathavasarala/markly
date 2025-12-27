# Markly Workspace Rules

## Tech Stack

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Vanilla CSS with Tailwind-like utility classes
- **State Management**: Zustand
- **Routing**: React Router v6
- **Icons**: Lucide React
- **Testing**: Vitest + React Testing Library

### Backend
- **Framework**: Flask (Python)
- **Database**: Supabase (PostgreSQL)
- **Authentication**: Supabase Auth
- **AI/ML**: OpenAI API
- **Content Extraction**: Jina Reader API
- **Server**: Gunicorn (production)

### Infrastructure
- **Container Registry**: Azure Container Registry (`marklyregistry.azurecr.io`)
- **Hosting**: Azure Web App for Containers
- **Version Control**: GitHub

---

## Development Workflow

### 1. Feature Development
1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Develop with tests**:
   - Write component tests for new UI components in `frontend/src/components/__tests__/`
   - Update existing tests when modifying components
   - Run tests before committing: `npm test` (in frontend directory)

3. **Commit with conventional commits**:
   ```bash
   git commit -m "feat: add new feature"
   git commit -m "fix: resolve bug"
   git commit -m "test: add tests for component"
   ```

4. **Push and create PR**:
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a PR on GitHub targeting `main`

### 2. Testing Requirements

#### Frontend Tests
- **Location**: `frontend/src/components/__tests__/`
- **Run tests**: `npm test` (from `frontend/` directory)
- **Coverage**: All new components should have basic render tests
- **Mock requirements**:
  - Mock Zustand stores (`useBookmarksStore`, `useUIStore`, `useAuthStore`)
  - Mock `lucide-react` icons
  - Mock API calls

#### Test Template for New Components
```typescript
import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'
import YourComponent from '../YourComponent'

// Mock stores
vi.mock('../../stores/yourStore', () => ({
    useYourStore: () => ({
        // mock store methods
    }),
}))

// Mock icons
vi.mock('lucide-react', () => ({
    IconName: () => <div data-testid="icon-name" />,
}))

describe('YourComponent', () => {
    it('renders correctly', () => {
        render(<YourComponent />)
        expect(screen.getByText('Expected Text')).toBeInTheDocument()
    })
})
```

### 3. Pre-Push Checklist
- [ ] All tests pass: `npm test`
- [ ] Linting passes: `npm run lint`
- [ ] Code builds successfully: `npm run build`
- [ ] Manual testing completed in local environment

---

## Deployment Strategy

### Image Repository
We use a **single image repository**: `markly-app`

### Tagging Strategy & Rollback Workflow

We use **multiple tags per build** to enable flexible deployments and easy rollbacks:

| Tag Type | Format | Purpose | Example |
|----------|--------|---------|---------|
| **Latest** | `latest` | Always points to current production | `markly-app:latest` |
| **Git SHA** | `<short-sha>` | Specific version for rollback | `markly-app:6f5551e` |
| **Feature** | `feature-<name>` | Test features before merging | `markly-app:feature-new-ui` |

### Production Deployment Workflow

#### Step 1: Deploy from `main` branch
```bash
# Get current git commit SHA
GIT_SHA=$(git rev-parse --short HEAD)

# Build with multiple tags
docker build --platform linux/amd64 \
  -t marklyregistry.azurecr.io/markly-app:latest \
  -t marklyregistry.azurecr.io/markly-app:$GIT_SHA \
  .

# Push all tags
docker push marklyregistry.azurecr.io/markly-app:latest
docker push marklyregistry.azurecr.io/markly-app:$GIT_SHA
```

**Result**: 
- `latest` tag moves to your new code
- Git SHA tag preserves the exact version
- Azure Web App (configured to use `latest`) automatically pulls the new image on restart

#### For Feature Testing (from feature branches):
```bash
# Use branch name as tag
BRANCH_NAME=$(git branch --show-current | sed 's/\//-/g')

docker build --platform linux/amd64 \
  -t marklyregistry.azurecr.io/markly-app:$BRANCH_NAME \
  .

docker push marklyregistry.azurecr.io/markly-app:$BRANCH_NAME
```

### Rollback Strategy

**Your Azure Web App should be configured to use a specific tag** (not `latest` for production stability).

#### Scenario 1: Safe Feature Deployment
```bash
# 1. Deploy feature to test
docker build --platform linux/amd64 \
  -t marklyregistry.azurecr.io/markly-app:feature-new-dashboard \
  .
docker push marklyregistry.azurecr.io/markly-app:feature-new-dashboard

# 2. Update Azure Web App to use feature tag
az webapp config container set \
  --name markly \
  --resource-group <your-resource-group> \
  --docker-custom-image-name marklyregistry.azurecr.io/markly-app:feature-new-dashboard

az webapp restart --name markly --resource-group <your-resource-group>

# 3. Test in production

# 4a. If successful: Merge to main and deploy as latest
git checkout main
git merge feature/new-dashboard
GIT_SHA=$(git rev-parse --short HEAD)
docker build --platform linux/amd64 \
  -t marklyregistry.azurecr.io/markly-app:latest \
  -t marklyregistry.azurecr.io/markly-app:$GIT_SHA \
  .
docker push --all-tags marklyregistry.azurecr.io/markly-app

# Update to latest
az webapp config container set \
  --name markly \
  --resource-group <your-resource-group> \
  --docker-custom-image-name marklyregistry.azurecr.io/markly-app:latest

# 4b. If failed: Rollback to previous git SHA
az webapp config container set \
  --name markly \
  --resource-group <your-resource-group> \
  --docker-custom-image-name marklyregistry.azurecr.io/markly-app:6f5551e

az webapp restart --name markly --resource-group <your-resource-group>
```

#### Scenario 2: Emergency Rollback
```bash
# Find previous working version
git log --oneline -5  # See recent commits

# Rollback to specific git SHA
az webapp config container set \
  --name markly \
  --resource-group <your-resource-group> \
  --docker-custom-image-name marklyregistry.azurecr.io/markly-app:<previous-sha>

az webapp restart --name markly --resource-group <your-resource-group>
```

**Recommended Production Configuration:**
- **Conservative**: Point Azure to a specific git SHA tag (e.g., `markly-app:6f5551e`)
  - Pro: Explicit control, no surprises
  - Con: Manual update needed for each deployment
  
- **Aggressive**: Point Azure to `latest`
  - Pro: Automatic updates on restart
  - Con: Need to be careful about what gets tagged as `latest`

**Best Practice**: Use git SHA tags for production, `latest` for staging/testing.

### Deployment Process

#### Step 1: Login to Azure Container Registry
```bash
docker login marklyregistry.azurecr.io -u marklyregistry
# Password: Get from Azure Portal > Container Registry > Access Keys
```

#### Step 2: Build and Push
```bash
# For production (from main branch)
GIT_SHA=$(git rev-parse --short HEAD)
docker build --platform linux/amd64 \
  -t marklyregistry.azurecr.io/markly-app:latest \
  -t marklyregistry.azurecr.io/markly-app:$GIT_SHA \
  .

docker push marklyregistry.azurecr.io/markly-app:latest
docker push marklyregistry.azurecr.io/markly-app:$GIT_SHA
```

#### Step 3: Update Azure Web App
**Option A: Via Azure Portal (Current Method)**
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Markly Web App**
3. Go to **Deployment Center**
4. Verify image tag is set to `markly-app:latest`
5. Click **Restart**
6. Wait 30-60 seconds for container to boot

**Option B: Via Azure CLI (Recommended for automation)**
```bash
# Install Azure CLI if needed: brew install azure-cli

# Login
az login

# Restart the web app
az webapp restart --name markly --resource-group <your-resource-group>

# Or update the container image and restart
az webapp config container set \
  --name markly \
  --resource-group <your-resource-group> \
  --docker-custom-image-name marklyregistry.azurecr.io/markly-app:latest

az webapp restart --name markly --resource-group <your-resource-group>
```

### Current State & Migration Plan

**Current Configuration:**
- Azure Web App is using: `markly-app:profile-revamp`
- Latest code has been pushed to: `markly-app:profile-revamp`

**Recommended Next Steps:**

1. **Verify current deployment** (after restart):
   - Test that the latest changes are working correctly
   
2. **Tag current state as a git SHA** for rollback capability:
   ```bash
   GIT_SHA=$(git rev-parse --short HEAD)
   docker tag marklyregistry.azurecr.io/markly-app:profile-revamp \
              marklyregistry.azurecr.io/markly-app:$GIT_SHA
   docker push marklyregistry.azurecr.io/markly-app:$GIT_SHA
   ```

3. **Migrate to git SHA-based deployment** (recommended):
   ```bash
   # In Azure Portal: Deployment Center
   # Change image tag from: markly-app:profile-revamp
   # To: markly-app:6f5551e (your current git SHA)
   ```
   
4. **For future deployments**, use this workflow:
   ```bash
   # After merging to main
   GIT_SHA=$(git rev-parse --short HEAD)
   docker build --platform linux/amd64 \
     -t marklyregistry.azurecr.io/markly-app:$GIT_SHA \
     .
   docker push marklyregistry.azurecr.io/markly-app:$GIT_SHA
   
   # Update Azure to new SHA
   az webapp config container set \
     --name markly \
     --resource-group <your-resource-group> \
     --docker-custom-image-name marklyregistry.azurecr.io/markly-app:$GIT_SHA
   
   az webapp restart --name markly --resource-group <your-resource-group>
   ```

5. **Cleanup old tags** (optional):
   - Delete `profile-revamp` tag once migrated to git SHA-based deployment

---

## Environment Variables

### Required Environment Variables (Backend)
Set these in Azure Web App > Configuration > Application Settings:

- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Supabase anon/public key
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key (for admin operations)
- `OPENAI_API_KEY`: OpenAI API key for AI features
- `JINA_API_KEY`: Jina Reader API key for content extraction
- `FLASK_ENV`: Set to `production`
- `FRONTEND_URL`: Your app's public URL (for CORS)

### Local Development
Create `backend/.env` file (never commit this):
```bash
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
OPENAI_API_KEY=your_openai_key
JINA_API_KEY=your_jina_key
FLASK_ENV=development
FRONTEND_URL=http://localhost:5173
```

---

## Code Style & Conventions

### Frontend
- Use functional components with hooks
- Prefer `const` over `let`
- Use TypeScript interfaces for props
- Use semantic color classes: `text-gray-900 dark:text-white` (not hardcoded colors)
- Mobile-first responsive design
- Memoize expensive components with `React.memo`

### Backend
- Follow PEP 8 style guide
- Use type hints where possible
- Keep routes RESTful
- Handle errors gracefully with proper HTTP status codes

### Git Commits
Use conventional commits:
- `feat:` - New feature
- `fix:` - Bug fix
- `test:` - Adding or updating tests
- `refactor:` - Code refactoring
- `docs:` - Documentation changes
- `chore:` - Maintenance tasks

---

## Troubleshooting

### Docker Build Issues
- **M1/M2/M3 Mac**: Always use `--platform linux/amd64`
- **Build cache issues**: Use `docker build --no-cache`
- **Permission denied**: Ensure Docker Desktop is running

### Azure Deployment Issues
- **Container won't start**: Check logs in Azure Portal > Log Stream
- **Authentication errors**: Verify environment variables are set
- **502 Bad Gateway**: Container is still starting, wait 60 seconds

### Test Failures
- **Missing mocks**: Ensure all Zustand stores and icons are mocked
- **Missing properties**: Check if interface definitions match (e.g., `is_public` in `Bookmark`)

---

## Quick Reference Commands

```bash
# Frontend
cd frontend
npm install          # Install dependencies
npm run dev          # Start dev server
npm test             # Run tests
npm run lint         # Run linter
npm run build        # Build for production

# Backend
cd backend
pip install -r requirements.txt  # Install dependencies
python app.py                    # Start dev server

# Docker
docker build --platform linux/amd64 -t marklyregistry.azurecr.io/markly-app:latest .
docker push marklyregistry.azurecr.io/markly-app:latest

# Git
git checkout -b feature/name     # Create feature branch
git add .                        # Stage changes
git commit -m "feat: message"    # Commit with convention
git push origin feature/name     # Push to remote
```
