"""
CodeGen Agent - Generates code, infrastructure, and configuration files.

The CodeGen Agent (Scaffolding Agent) creates complete microservice projects
including application code, infrastructure as code, CI/CD pipelines, and
Kubernetes manifests.
"""

import json
import os
import uuid
import base64
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from jinja2 import Environment, FileSystemLoader, select_autoescape
import sys
sys.path.append('../..')

from common.agent_base import BaseAgent
from common.version import __version__
from common.graphs import build_codegen_graph
from common.schemas.workflow import ServiceScaffoldRequest
from common.mcp_client import GitHubMCPClient


app = FastAPI(
    title="CodeGen Agent",
    description="Generates microservice code, infrastructure, and CI/CD configurations",
    version=__version__
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CodeGenAgent(BaseAgent):
    """CodeGen Agent implementation."""

    def __init__(self):
        super().__init__(agent_name="codegen")

        # MCP GitHub client
        self.github_client: Optional[GitHubMCPClient] = None

        # Jinja2 template environment
        template_dir = Path(__file__).parent.parent.parent.parent / "templates"
        self.template_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )

        self.graph = build_codegen_graph(self)
        self.logger.info("CodeGen Agent initialized with LangGraph workflow")

    async def _initialize_github(self):
        """Initialize MCP GitHub client."""
        if self.github_client:
            return

        try:
            self.github_client = GitHubMCPClient()
            self.logger.info("MCP GitHub client initialized")
        except Exception as e:
            self.logger.warning(f"Could not initialize MCP GitHub client: {e}")
            self.github_client = None

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a code generation task."""
        input_params = task.get('input_params', {})

        # Generate microservice
        result = await self.generate_microservice(
            service_name=input_params['service_name'],
            language=input_params.get('language', 'python'),
            database=input_params.get('database', 'postgresql'),
            api_type=input_params.get('api_type', 'rest'),
            environment=input_params.get('environment', 'dev')
        )

        return result

    async def generate_microservice(
        self,
        service_name: str,
        language: str,
        database: str,
        api_type: str,
        environment: str
    ) -> Dict[str, Any]:
        """
        Generate complete microservice project.

        Uses LangGraph to orchestrate: init_github -> templates -> enhance -> store -> push -> readme

        Args:
            service_name: Service name (kebab-case)
            language: Programming language
            database: Database type
            api_type: API type (rest, grpc, graphql)
            environment: Target environment

        Returns:
            Generation results including repository URL
        """
        self.logger.info(f"Generating {language} microservice: {service_name}")

        result = await self.graph.ainvoke({
            "service_name": service_name,
            "language": language,
            "database": database,
            "api_type": api_type,
            "environment": environment,
        })

        return {
            'service_name': service_name,
            'repository_url': result.get('repo_url', ''),
            'artifact_s3_key': result.get('artifact_key', ''),
            'files_generated': result.get('files_generated', 0),
            'language': language,
            'database': database
        }

    async def _generate_from_templates(
        self,
        service_name: str,
        language: str,
        database: str,
        api_type: str
    ) -> Dict[str, str]:
        """
        Generate files from Jinja2 templates.

        Args:
            service_name: Service name
            language: Programming language
            database: Database type
            api_type: API type

        Returns:
            Dictionary mapping file paths to content
        """
        files = {}

        # Context for template rendering
        context = {
            'service_name': service_name,
            'service_name_snake': service_name.replace('-', '_'),
            'service_name_pascal': ''.join(word.capitalize() for word in service_name.split('-')),
            'database': database,
            'api_type': api_type,
            'timestamp': datetime.utcnow().isoformat()
        }

        # Generate based on language
        if language == 'python':
            files.update(await self._generate_python_fastapi(context))
        elif language == 'nodejs':
            files.update(await self._generate_nodejs_express(context))
        elif language == 'go':
            files.update(await self._generate_go_gin(context))
        else:
            raise ValueError(f"Unsupported language: {language}")

        # Generate common files
        files.update(await self._generate_common_files(context))

        return files

    async def _generate_python_fastapi(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Generate Python FastAPI project."""
        service_name = context['service_name_snake']

        return {
            f'{service_name}/__init__.py': '',
            f'{service_name}/main.py': '''"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="{{ service_name }}",
    description="{{ service_name }} microservice",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"service": "{{ service_name }}", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/ready")
async def ready():
    return {"status": "ready"}
'''.replace('{{ service_name }}', context['service_name']),

            f'{service_name}/models.py': f'''"""Database models."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Item(Base):
    """Example Item model."""
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
''',

            f'{service_name}/schemas.py': '''"""Pydantic schemas."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class ItemCreate(ItemBase):
    pass

class Item(ItemBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
''',

            'requirements.txt': '''fastapi==0.109.0
uvicorn[standard]==0.27.0
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
pydantic==2.5.3
python-dotenv==1.0.0
alembic==1.13.1
''',

            'Dockerfile': f'''FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY {service_name}/ /app/{service_name}/

EXPOSE 8000

CMD ["uvicorn", "{service_name}.main:app", "--host", "0.0.0.0", "--port", "8000"]
''',
        }

    async def _generate_nodejs_express(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Generate Node.js Express project."""
        return {
            'src/index.js': '''const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());

app.get('/', (req, res) => {
  res.json({ service: '{{ service_name }}', status: 'running' });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(port, () => {
  console.log(`Server running on port ${port}`);
});
'''.replace('{{ service_name }}', context['service_name']),

            'package.json': json.dumps({
                'name': context['service_name'],
                'version': '1.0.0',
                'main': 'src/index.js',
                'scripts': {
                    'start': 'node src/index.js',
                    'dev': 'nodemon src/index.js'
                },
                'dependencies': {
                    'express': '^4.18.2',
                    'pg': '^8.11.3'
                },
                'devDependencies': {
                    'nodemon': '^3.0.2'
                }
            }, indent=2),

            'Dockerfile': '''FROM node:18-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install --production

COPY src/ ./src/

EXPOSE 3000

CMD ["npm", "start"]
'''
        }

    async def _generate_go_gin(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Generate Go Gin project."""
        return {
            'main.go': '''package main

import (
    "github.com/gin-gonic/gin"
)

func main() {
    r := gin.Default()

    r.GET("/", func(c *gin.Context) {
        c.JSON(200, gin.H{
            "service": "{{ service_name }}",
            "status":  "running",
        })
    })

    r.GET("/health", func(c *gin.Context) {
        c.JSON(200, gin.H{"status": "healthy"})
    })

    r.Run(":8080")
}
'''.replace('{{ service_name }}', context['service_name']),

            'go.mod': f'''module {context['service_name']}

go 1.21

require github.com/gin-gonic/gin v1.9.1
''',

            'Dockerfile': '''FROM golang:1.21-alpine AS builder

WORKDIR /app
COPY . .
RUN go build -o main .

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/main .

EXPOSE 8080
CMD ["./main"]
'''
        }

    async def _generate_common_files(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Generate common files (CI/CD, K8s, etc.)."""
        service_name = context['service_name']

        return {
            '.gitignore': '''# Python
__pycache__/
*.py[cod]
*$py.class
venv/
.env

# Node
node_modules/
dist/

# Go
*.exe
*.dll
*.so
*.dylib

# IDEs
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
''',

            '.github/workflows/ci.yml': f'''name: Gitflow CI/CD

on:
  push:
    branches:
      - develop
      - 'release/**'
      - 'hotfix/**'
  pull_request:
    branches:
      - develop
      - main

jobs:
  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest --cov --cov-report=term-missing

  build:
    name: Build
    runs-on: ubuntu-latest
    needs: test
    if: github.event_name == 'push'
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker image
        run: docker build -t {service_name}:${{{{ github.sha }}}} .

  deploy-dev:
    name: Deploy to Dev
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/develop'
    steps:
      - name: Deploy
        run: |
          echo "Deploying {service_name} to development"
          echo "Commit: ${{{{ github.sha }}}}"

  deploy-staging:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    needs: build
    if: startsWith(github.ref, 'refs/heads/release/')
    steps:
      - name: Deploy
        run: |
          echo "Deploying {service_name} to staging"
          echo "Release: ${{{{ github.ref_name }}}}"
''',

            'k8s/deployment.yaml': f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: {service_name}
  labels:
    app: {service_name}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: {service_name}
  template:
    metadata:
      labels:
        app: {service_name}
    spec:
      containers:
      - name: {service_name}
        image: {service_name}:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: {service_name}-secrets
              key: database-url
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
''',

            'k8s/service.yaml': f'''apiVersion: v1
kind: Service
metadata:
  name: {service_name}
spec:
  selector:
    app: {service_name}
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
''',

            'docker-compose.yml': f'''version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/{service_name}
    depends_on:
      - db

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB={service_name}
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
''',
        }

    async def _enhance_with_ai(
        self,
        files: Dict[str, str],
        service_name: str,
        language: str
    ) -> Dict[str, str]:
        """
        Use Claude AI to enhance generated code with best practices.

        Args:
            files: Generated files
            service_name: Service name
            language: Programming language

        Returns:
            Enhanced files
        """
        # For now, return files as-is
        # In production, could use Claude to add better error handling,
        # logging, documentation, etc.
        self.logger.info("AI enhancement placeholder - returning original files")
        return files

    async def _generate_readme(
        self,
        service_name: str,
        language: str,
        database: str,
        api_type: str
    ) -> str:
        """Generate README.md using Claude AI."""
        prompt = f"""Generate a comprehensive README.md for a microservice with these specifications:

Service Name: {service_name}
Language: {language}
Database: {database}
API Type: {api_type}

Include:
1. Service overview
2. Getting started (prerequisites, installation)
3. Running locally with Docker Compose
4. API endpoints (with examples)
5. Environment variables
6. Testing
7. Deployment
8. Contributing

Use markdown formatting. Be concise but complete."""

        try:
            readme = await self.call_claude(prompt, max_tokens=2000)
            return readme
        except Exception as e:
            self.logger.error(f"Error generating README: {e}")
            # Fallback README
            return f"""# {service_name}

A {language} microservice with {database} database.

## Getting Started

```bash
# Install dependencies
docker-compose up -d

# Access the service
curl http://localhost:8000/health
```

## API Endpoints

- `GET /` - Service info
- `GET /health` - Health check
- `GET /ready` - Readiness check

## Environment Variables

- `DATABASE_URL` - Database connection string

## Development

See documentation for more details.
"""

    async def _store_artifacts(self, key: str, files: Dict[str, str]):
        """Store generated files in S3."""
        try:
            # Combine all files into a JSON structure
            artifact = json.dumps(files, indent=2)

            # Get bucket name - base class will prepend environment automatically
            aws_account_id = os.getenv('AWS_ACCOUNT_ID', '773550624765')
            bucket_name = f"agent-artifacts-{aws_account_id}"

            await self.store_artifact_s3(
                bucket=bucket_name,
                key=key,
                data=artifact.encode('utf-8'),
                metadata={
                    'agent': 'codegen',
                    'file_count': str(len(files))
                }
            )
            self.logger.info(f"Stored artifacts in S3: s3://{bucket_name}/{key}")
        except Exception as e:
            self.logger.warning(f"Could not store artifacts in S3: {e}")

    async def _create_and_push_repository(
        self,
        service_name: str,
        files: Dict[str, str]
    ) -> str:
        """
        Create GitHub repository and push generated code.

        Args:
            service_name: Service name
            files: Generated files

        Returns:
            Repository URL
        """
        if not self.github_client:
            self.logger.warning("MCP GitHub client not available, skipping repo creation")
            return f"https://github.com/placeholder/{service_name}"

        repo_url = ""
        repo_exists = False

        try:
            # Try to create repository via MCP
            repo_result = await self.github_client.create_repository(
                name=service_name,
                description=f'Auto-generated microservice: {service_name}',
                private=True,
                auto_init=False
            )

            repo_url = repo_result.get('html_url', '')
            self.logger.info(f"Created repository via MCP: {repo_url}")

        except Exception as e:
            error_str = str(e)

            # Check if repository already exists (422 error)
            if "422" in error_str or "already exists" in error_str.lower():
                self.logger.info(f"Repository {service_name} already exists, will push files to it")
                repo_exists = True

                # Try to get the existing repository URL
                try:
                    repo_info = await self.github_client.get_repository(service_name)
                    repo_url = repo_info.get('html_url', f"https://github.com/placeholder/{service_name}")
                except Exception as get_error:
                    self.logger.warning(f"Could not get repository info: {get_error}")
                    repo_url = f"https://github.com/placeholder/{service_name}"
            else:
                self.logger.error(f"Error creating GitHub repository via MCP: {e}")
                return f"https://github.com/placeholder/{service_name}"

        # Push files to repository (whether new or existing)
        try:
            files_pushed = 0
            for file_path, content in files.items():
                try:
                    await self.github_client.create_file(
                        repo_name=service_name,
                        file_path=file_path,
                        content=content,
                        message=f"Add {file_path}" if not repo_exists else f"Update {file_path}",
                        branch="main"
                    )
                    files_pushed += 1
                    self.logger.info(f"{'Created' if not repo_exists else 'Updated'} file via MCP: {file_path}")
                except Exception as e:
                    self.logger.warning(f"Could not create/update file {file_path} via MCP: {e}")
                    continue

            self.logger.info(f"Successfully pushed {files_pushed}/{len(files)} files to {service_name}")
            return repo_url

        except Exception as e:
            self.logger.error(f"Error pushing files to repository: {e}")
            return repo_url if repo_url else f"https://github.com/placeholder/{service_name}"


# Initialize agent
codegen_agent = CodeGenAgent()


@app.post("/generate")
@app.post("/dev/generate")
async def generate_microservice(request: ServiceScaffoldRequest):
    """Generate a new microservice."""
    try:
        result = await codegen_agent.generate_microservice(
            service_name=request.service_name,
            language=request.language,
            database=request.database,
            api_type=request.api_type,
            environment=request.environment
        )
        return result
    except Exception as e:
        codegen_agent.logger.error(f"Error generating microservice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/health")
@app.get("/dev/health")
@app.get("/codegen/health")
@app.get("/dev/codegen/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "codegen",
        "version": __version__
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
