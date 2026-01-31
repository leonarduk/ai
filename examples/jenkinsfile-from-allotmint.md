# Example Jenkinsfile from Separate Project

**Note:** This Jenkinsfile is from the `allotmint` project and is kept here as a reference example of CI/CD pipeline configuration.

## What This Shows

This demonstrates a multi-language CI/CD pipeline pattern:
- Parallel test execution (Python, Node.js, Java)
- Docker-based build agents
- Code coverage reporting
- Conditional stages

## Original Source

From: `https://github.com/leonarduk/allotmint`

This is NOT the CI/CD for ai-systems-lab. For this repository's CI/CD, see `.github/workflows/` (when implemented).

---

## The Jenkinsfile

```groovy
pipeline {
    agent none

    stages {
        stage('Checkout') {
            agent any
            steps {
                cleanWs()
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/main']],
                    userRemoteConfigs: [[
                        url: 'https://github.com/leonarduk/allotmint.git',
                        credentialsId: 'GITHUB_TOKEN'
                    ]]
                ])
            }
        }

        stage('Build & Test') {
            parallel {
                stage('Python Tests') {
                    agent {
                        docker {
                            image: 'python:3.11'
                            args '-u root'
                        }
                    }
                    steps {
                        sh '''
                            apt-get update && apt-get install -y git
                            python --version
                            pip install --upgrade pip setuptools wheel
                            pip install -r requirements.txt
                            pip install pytest pytest-cov
                            pip install jinja2 python-multipart
                            pytest backend/tests --cov=backend --cov-report=html
                        '''
                    }
                    post {
                        always {
                            archiveArtifacts artifacts: 'htmlcov/**', fingerprint: true
                            publishHTML([
                                allowMissing: false,
                                keepAll: true,
                                alwaysLinkToLastBuild: true,
                                reportDir: 'htmlcov',
                                reportFiles: 'index.html',
                                reportName: 'Python Coverage Report'
                            ])
                        }
                    }
                }

                stage('Node.js Build') {
                    agent {
                        docker {
                            image: 'node:20'
                            args '-u root'
                        }
                    }
                    steps {
                        sh '''
                            apt-get update && apt-get install -y git
                            node --version
                            cd frontend
                            npm ci   # Use ci for clean install from package-lock.json
                            npm test
                        '''
                    }
                }

                stage('Java Build') {
                    when {
                        expression { fileExists('pom.xml') }
                    }
                    agent {
                        docker {
                            image: 'maven:3.9.6-eclipse-temurin-17'
                            args '-u root'
                        }
                    }
                    steps {
                        sh '''
                            apt-get update && apt-get install -y git
                            mvn clean install
                        '''
                    }
                }
            }
        }
    }
}
```

## Adaptation Notes

If adapting this for ai-systems-lab:
1. Update repository URL to this repo
2. Adjust test commands for MCP servers
3. Remove Node.js and Java stages (Python only)
4. Consider GitHub Actions instead (more modern)
