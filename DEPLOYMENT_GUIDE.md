# The Beginner's Guide to Deploying Full-Stack Apps
*(A Learning Resource based on the Markly Project)*

Deploying an application means taking code from your laptop and making it accessible to the world on a server. This guide breaks down the "Containerized" approach we used for Markly (Azure + Docker) and contrasts it with other popular methods like Vercel.

---

## 1. The Core Concept: Containers (The "Suitcase")

Imagine moving houses. You have clothes, furniture, and kitchenware.
*   **Without Containers:** You throw everything loose into a truck. When you arrive, you realize the new house has different shaped cupboards, or you forgot the screws for the bed.
*   **With Containers (Docker):** You pack everything into standard boxes. You know exactly what fits. When you arrive, you just put the boxes down. It doesn't matter if the house is a mansion or a shack; the boxes remain the same.

**In deployment:**
*   **Docker** puts your code, libraries (Supabase, OpenAI), and runtime (Python, Node.js) into a "Container Image".
*   Be it your laptop, an Azure server, or AWS, the code runs **exactly** the same way because it never leaves its box.

### The Dockerfile: The Packing List
The `Dockerfile` is the instruction manual for packing the box. We used a **Multi-Stage Build**, which is a pro move:
1.  **Stage 1 (Node.js)**: We install npm tools, build the code, and create the static website files (`.html`, `.js`, `.css`).
2.  **Stage 2 (Python)**: We start fresh with a lightweight Python environment. We *discard* all the heavy npm tools and *only copy* the final static files from Stage 1.
3.  **Result**: A tiny, efficient image containing only what is needed to *run* the app, not *build* it.

---

## 2. The Cloud Components

### Azure Container Registry (ACR)
*   **What it is:** A secure warehouse for your "boxes" (Docker Images).
*   **Why we need it:** Your laptop cannot send the file directly to the Web App easily. Instead, you upload ("Push") the image to the Registry. The Web App then downloads ("Pulls") it.
*   **Analogy:** You serve your code to the cloud like a chef serves food to a pass. The waiters (servers) pick it up from there.

### Azure Web App
*   **What it is:** The actual computer/server that runs your container.
*   **Configuration:**
    *   **Environment Variables:** These are the secrets (API Keys, URLs) that we inject into the container at runtime. We never "bake" them into the image for security reasons.
    *   **Startup Command:** We verify how the app starts (`gunicorn app:create_app()`).

---

## 3. Daily Workflow: How to Update Your App

When you make changes to your code, you usually want to do two things:
1.  **Save your work history** (Git).
2.  **Update the live website** (Azure Docker).

These are separate actions. You can save to git without deploying to Azure, and vice-versa (though usually you want both).

### Part A: Save Code (Git)
The industry-standard way to save progress and collaborate.

```bash
# 1. Stage all your changes
git add .

# 2. Commit with a meaningful message
git commit -m "feat: added jina scraper and cleaned up UI"

# 3. Push to the cloud (GitHub)
git push origin main
```

### Part B: Deploy to Production (Azure Docker)
This packages your code into a "container" and ships it to Azure.

**1. Login to the Registry (Once per session)**
```bash
docker login marklyregistry.azurecr.io -u marklyregistry
```

**2. The "One-Liner" Build & Push**
*Crucial: If you are on an M1/M2/M3 Mac, you MUST include the `--platform linux/amd64` flag so it works on Azure's Intel/AMD servers.*

```bash
# Build and Push in one go
docker build --platform linux/amd64 -t marklyregistry.azurecr.io/markly:latest . && \
docker push marklyregistry.azurecr.io/markly:latest
```

**3. Final Step: Manual Restart**
*   Go to: [Azure Portal](https://portal.azure.com)
*   Find: **Markly Web App**
*   Action: Click **Restart**
*   *Note: It takes about 30-60 seconds for the container to "boot up" after a restart.*

---

## 4. Alternative: Deploying to Vercel (Serverless)

Vercel is incredibly popular for React apps. Why didn't we use it?

### How Vercel Works
Vercel specializes in **Serverless** and **Static** hosting.
*   **Frontend:** It takes your React code, builds it, and distributes it to a Content Delivery Network (CDN) globally. It's incredibly fast.
*   **Backend:** It expects your backend API to be broken down into tiny "functions" (javascript/typescript usually) located in an `/api` folder.

### The Challenge with Python
Markly has a robust Python (Flask) backend running long tasks (scraping, AI analysis).
*   **On Vercel:** You would have to rewrite your Flask app into Python "Serverless Functions".
*   **Serverless Limitations:** Functions usually have a timeout (e.g., 10 seconds). If your AI Summary takes 15 seconds, the function is killed.
*   **State:** A standard Flask app stays running in memory. Serverless functions wake up, run, and die.

### If you wanted to move to Vercel tomorrow:
1.  **Split the Project:** You would host the Frontend (`/frontend`) on Vercel.
2.  **Keep the Backend:** You would *still* need to host the Python Backend (`/backend`) on Azure, Render, or Railway (platforms that support Docker or Python services).
3.  **Connect them:** You would tell the Vercel Frontend to talk to `https://markly-backend.azurewebsites.net` instead of `localhost`.

---

## Summary Checklist for Success

- [ ] **Docker is Running:** Required to build images locally.
- [ ] **Wrong Architecture:** If you are on an M1/M2 Mac, always add `--platform linux/amd64` to your build command so Azure (which uses standard Linux chips) can read it.
- [ ] **Environment Variables:** If the app crashes on start, 99% of the time it is missing an ENV variable in the Cloud dashboard.
- [ ] **Cold Starts:** On "Basic" or "Free" plans, your app goes to sleep if no one uses it. The first visit might take 20s to wake up. "Always On" feature (available on paid Standard plans) fixes this.

This architecture (Docker + Cloud Web App) is the industry standard for full-stack apps because it is robust, portable, and handles complex backends easily.
