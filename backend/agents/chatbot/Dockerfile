FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common module (dependency for agents)
COPY ../common /app/common

# Copy agent code
COPY . /app/agents/chatbot

WORKDIR /app

# Expose port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8003/health')"

# Run application
CMD ["python", "-m", "uvicorn", "agents.chatbot.main:app", "--host", "0.0.0.0", "--port", "8003"]
