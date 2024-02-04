pipeline {
    agent any

    // Define environment variables
    environment {
        ECR_REGISTRY = "your_ecr_registry"          // Your ECR registry URL
        TIMESTAMP = new Date().format('yyyyMMdd_HHmmss')
        IMAGE_TAG = "${env.BUILD_NUMBER}_${TIMESTAMP}"  // Tag for the Docker image
        ECR_REGION = "your_ecr_region"              // Your ECR region
        AWS_CREDENTIALS_ID = 'AWS credentials'      // ID of AWS credentials in Jenkins
        KUBE_CONFIG_CRED = 'KUBE_CONFIG_CRED'       // ID of Kubernetes config credentials in Jenkins
        CLUSTER_NAME = "k8s-main"                   // Name of your Kubernetes cluster
        CLUSTER_REGION = "your_cluster_region"      // Region of your Kubernetes cluster
        GIT_CREDENTIALS_ID = "GIT_CREDENTIALS_ID"   // ID of Git credentials in Jenkins
    }

    stages {
        stage('Login to AWS ECR') {
            steps {
                script {
                    // Login to AWS ECR
                    withCredentials([aws(credentialsId: AWS_CREDENTIALS_ID, accessKeyVariable: 'AWS_ACCESS_KEY_ID', secretKeyVariable: 'AWS_SECRET_ACCESS_KEY')]) {
                        sh 'aws ecr get-login-password --region ${ECR_REGION} | docker login --username AWS --password-stdin ${ECR_REGISTRY}'
                    }
                }
            }
        }

        stage('Build and Push') {
            steps {
                script {
                    echo "IMAGE_TAG: ${IMAGE_TAG}"
                    // Build and push Docker image to ECR
                    dockerImage = docker.build("${ECR_REGISTRY}/yolo5-team3-ecr:${IMAGE_TAG}")
                    dockerImage.push()
                }
            }
        }

        stage('Update Deployment and Push to GitHub') {
            steps {
                script {
                    // Update Kubernetes deployment YAML and push changes to GitHub
                    withCredentials([usernamePassword(credentialsId: 'GIT_CREDENTIALS_ID', passwordVariable: 'GIT_PASSWORD', usernameVariable: 'GIT_USERNAME')]) {
                        def repoDir = 'yolo-k8s'
                        if (!fileExists("${repoDir}/.git")) {
                            sh "git clone https://github.com/your_username/yolo-k8s.git ${repoDir}"  // Clone the Git repository if it doesn't exist
                        }

                        dir(repoDir) {
                            sh 'git checkout argo-releases'
                            sh 'git fetch --all'
                            sh 'git reset --hard origin/argo-releases'
                            try {
                                sh 'git merge origin/main' // Merge changes from main branch
                            } catch (Exception e) {
                                echo "Merge encountered issues: ${e.getMessage()}"
                                sh 'git merge --abort'
                                error "Merging from main to argo-releases failed. Please resolve conflicts manually."
                            }
                            sh "sed -i 's|image: .*|image: ${ECR_REGISTRY}/yolo5-team3-ecr:${IMAGE_TAG}|' yolo5-deployment.yaml"  // Update image tag in deployment YAML
                            sh 'git config user.email "your_email"'  // Configure Git user email
                            sh 'git config user.name "your_username"' // Configure Git username
                            
                            sh 'git add yolo5-deployment.yaml'
                            sh 'git commit -m "Update image tag to ${IMAGE_TAG}"'
                            sh 'git push https://$GIT_USERNAME:$GIT_PASSWORD@github.com/your_username/yolo-k8s.git argo-releases'
                        }
                    }
                }
            }
        }
    }

    // Clean up Docker images
    post {
        always {
            sh 'docker rmi $(docker images -q) -f || true'
        }
    }
}
