#!/usr/bin/env python3
"""Test the updated pipeline converter to verify it generates proper workflows."""

import sys
sys.path.insert(0, 'backend/agents/migration')
sys.path.insert(0, 'backend/agents/common')

from main import JenkinsPipelineConverter
import yaml

# The petclinic Jenkins pipeline
jenkinsfile = """
pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps {
                script {
                    echo 'Checking out Spring PetClinic from GitHub...'
                    git branch: 'main',
                        url: 'https://github.com/spring-projects/spring-petclinic.git'
                }
            }
        }
        stage('Build') {
            steps {
                script {
                    echo 'Building Spring PetClinic...'
                    if (isUnix()) {
                        sh 'chmod +x mvnw'
                        sh './mvnw clean compile'
                    } else {
                        bat 'mvnw.cmd clean compile'
                    }
                }
            }
        }
        stage('Test') {
            steps {
                script {
                    echo 'Running tests...'
                    if (isUnix()) {
                        sh './mvnw test'
                    } else {
                        bat 'mvnw.cmd test'
                    }
                }
            }
        }
        stage('Package') {
            steps {
                script {
                    echo 'Packaging application...'
                    if (isUnix()) {
                        sh './mvnw package -DskipTests'
                    } else {
                        bat 'mvnw.cmd package -DskipTests'
                    }
                }
            }
        }
    }
}
"""

# Initialize converter
converter = JenkinsPipelineConverter()

# Parse and convert
pipeline_data = converter.parse_jenkinsfile(jenkinsfile)
print("=== Parsed Pipeline Data ===")
print(f"Agent: {pipeline_data['agent']}")
print(f"Number of stages: {len(pipeline_data['stages'])}")
print(f"Git URL: {pipeline_data.get('git_url', 'Not detected')}")
print(f"Git Branch: {pipeline_data.get('git_branch', 'Not detected')}")
print()

for stage in pipeline_data['stages']:
    print(f"Stage: {stage['name']}")
    print(f"  Steps: {len(stage['steps'])}")
    for step in stage['steps']:
        print(f"    - {step[:60]}...")
    print()

# Convert to GitHub Actions
workflow = converter.convert_to_github_actions(pipeline_data, 'petclinic-pipeline')

print("\n=== Generated GitHub Actions Workflow ===")
print(yaml.dump(workflow, default_flow_style=False))

# Check for key features
print("\n=== Verification ===")
checks = {
    "Has checkout job": 'checkout' in workflow['jobs'] or any('checkout' in str(job).lower() for job in workflow['jobs'].values()),
    "Has git repository URL": any('repository' in str(job) for job in workflow['jobs'].values()),
    "Has Java setup": any('setup-java' in str(job) for job in workflow['jobs'].values()),
    "Has mvnw commands": any('mvnw' in str(job) for job in workflow['jobs'].values()),
    "Has artifact upload": any('upload-artifact' in str(job) for job in workflow['jobs'].values()),
}

for check, result in checks.items():
    status = "✓" if result else "✗"
    print(f"{status} {check}: {result}")
