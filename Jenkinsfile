pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Setup venv') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                '''
            }
        }

        stage('Render Configs') {
            steps {
                sh '''
                    . venv/bin/activate
                    python3 render.py
                '''
            }
        }

        stage('Healthcheck (live lab)') {
            steps {
                sh '''
                    . venv/bin/activate
                    python3 healthcheck.py
                '''
            }
        }
    }

    post {
        success {
            archiveArtifacts artifacts: 'rendered/*.cfg', fingerprint: true
        }
        failure {
            echo 'Pipeline failed — check console output above.'
        }
    }
}