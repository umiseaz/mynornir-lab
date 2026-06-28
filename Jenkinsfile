pipeline {
    agent any

    stages {
        stage('Render Configs') {
            steps {
                sh '''
                    # 1. Spin up the internal virtual environment
                    python3 -m venv venv
                    . venv/bin/activate
                    
                    # 2. Upgrade pip and pull down your consolidated requirements
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    
                    # 3. Run the rendering engine
                    python3 render.py
                '''
            }
        }
    }
}