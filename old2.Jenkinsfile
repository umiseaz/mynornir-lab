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

        stage('Validate') {
            steps {
                sh '''
                    . venv/bin/activate
                    python3 ci/check_vrf_consistency.py
                '''
            }
        }

        stage('Deploy (main only)') {
            when {
                branch 'main'
            }
            steps {
                sh '''
                    . venv/bin/activate
                    python3 healthcheck.py
                    python3 deploy.py --yes
                    python3 healthcheck.py
                    python3 save.py
                '''
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'rendered/*.cfg', fingerprint: true, allowEmptyArchive: true
        }
        success {
            echo "Build succeeded on branch ${env.BRANCH_NAME}"
        }
        failure {
            echo "Build failed on branch ${env.BRANCH_NAME} — check console output above."
        }
    }
}