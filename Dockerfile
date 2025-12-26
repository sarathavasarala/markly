# Build Stage for Frontend
FROM node:18-alpine as build-frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Runtime Stage for Backend
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies if needed (e.g. for some python packages)
# RUN apt-get update && apt-get install -y gcc

# Copy backend requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# Copy backend code
COPY backend/ .

# Copy built frontend assets from the build stage to a 'static' directory in the backend
# We rename 'dist' to 'static' to match Flask's default static folder approach (or we configure Flask to point to it)
COPY --from=build-frontend /app/frontend/dist ./static

# Expose the port
EXPOSE 8000

# Set environment variables
ENV FLASK_APP=app.py
# Use 0.0.0.0 to bind to all interfaces within the container
ENV PORT=8000

# Run with Gunicorn
# 4 workers is a reasonable starting point; adjust based on SKU
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:create_app()"]
