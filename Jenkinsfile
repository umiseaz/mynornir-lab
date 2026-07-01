pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Quick Syntax Checks') {
            steps {
                sh '''
                    echo "── Python syntax check ──"
                    python3 -m py_compile render.py deploy.py save.py healthcheck.py collect.py test_template.py ci/check_vrf_consistency.py

                    echo "── YAML lint (host_vars, inventory) ──"
                    python3 -m yamllint -d "{extends: default, rules: {line-length: disable, document-start: disable}}" host_vars/ inventory/

                    echo "── Jinja2 template syntax check ──"
                    python3 -c "
import sys
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

env = Environment(loader=FileSystemLoader('templates/'))
failed = False
import os
for f in os.listdir('templates/'):
    if f.endswith('.j2'):
        try:
            env.get_template(f)
            print(f'  [OK] {f}')
        except TemplateSyntaxError as e:
            print(f'  [FAIL] {f}: {e}')
            failed = True
sys.exit(1 if failed else 0)
"
                '''
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