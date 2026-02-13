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

    post {
        success {
            echo 'Build completed successfully!'
            archiveArtifacts artifacts: 'target/*.jar', allowEmptyArchive: true
        }
        failure {
            echo 'Build failed!'
        }
        always {
            echo 'Cleaning up workspace...'
        }
    }
}
