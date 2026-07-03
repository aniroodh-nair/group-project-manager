pipeline {
    agent any

    options {
        ansiColor('xterm')
        timestamps()
        skipDefaultCheckout()
    }

    parameters {
        booleanParam(name: 'DEPLOY', defaultValue: false, description: 'Run deployment after a successful build')
        string(name: 'DOCKER_REGISTRY', defaultValue: '', description: 'Optional Docker registry to tag and push the built image')
        string(name: 'DOCKER_CREDENTIALS_ID', defaultValue: '', description: 'Jenkins credential ID for the Docker registry login')
    }

    environment {
        FLASK_APP = 'backend.app'
        FLASK_ENV = 'production'
        IMAGE_NAME = 'group-project-manager'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Prepare environment') {
            steps {
                sh 'python -m pip install --upgrade pip'
                sh 'pip install -r requirements.txt'
            }
        }

        stage('Validate Python') {
            steps {
                sh 'python -m compileall backend'
                sh 'python -m py_compile backend/app.py backend/auth.py backend/grouping.py backend/models.py'
            }
        }

        stage('Build Docker image') {
            steps {
                script {
                    def tag = "${env.IMAGE_NAME}:${env.BUILD_NUMBER ?: 'latest'}"
                    sh "docker build -t ${tag} ."
                    env.BUILT_IMAGE = tag
                }
            }
        }

        stage('Publish Docker image') {
            when {
                expression { return params.DOCKER_REGISTRY?.trim() }
            }
            steps {
                script {
                    def registry = params.DOCKER_REGISTRY.trim()
                    def localTag = env.BUILT_IMAGE ?: "${env.IMAGE_NAME}:${env.BUILD_NUMBER ?: 'latest'}"
                    def remoteTag = "${registry}/${localTag}"

                    if (params.DOCKER_CREDENTIALS_ID?.trim()) {
                        withCredentials([usernamePassword(credentialsId: params.DOCKER_CREDENTIALS_ID, usernameVariable: 'REGISTRY_USER', passwordVariable: 'REGISTRY_PASS')]) {
                            sh "echo ${REGISTRY_PASS} | docker login ${registry} --username ${REGISTRY_USER} --password-stdin"
                        }
                    }

                    sh "docker tag ${localTag} ${remoteTag}"
                    sh "docker push ${remoteTag}"
                }
            }
        }

        stage('Deploy') {
            when {
                expression { return params.DEPLOY }
            }
            steps {
                sh 'docker-compose down || true'
                sh 'docker-compose up -d --build'
            }
        }
    }

    post {
        success {
            echo 'Pipeline completed successfully.'
        }
        failure {
            echo 'Pipeline failed. Check the log output for errors.'
        }
    }
}
