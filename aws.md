# AWS Deployment Guide - Graduated Autonomy Engine

This guide provides step-by-step instructions for deploying the Graduated Autonomy Engine to AWS cloud services.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Option 1: AWS Elastic Beanstalk (Simplest)](#option-1-aws-elastic-beanstalk-simplest)
4. [Option 2: AWS ECS with Fargate (Containerized)](#option-2-aws-ecs-with-fargate-containerized)
5. [Option 3: AWS EC2 (Manual Deployment)](#option-3-aws-ec2-manual-deployment)
6. [Option 4: Serverless with AWS Lambda (API Only)](#option-4-serverless-with-aws-lambda-api-only)
7. [Frontend Deployment Options](#frontend-deployment-options)
8. [Database Configuration](#database-configuration)
9. [Environment Variables](#environment-variables)
10. [Security Considerations](#security-considerations)
11. [Monitoring and Logging](#monitoring-and-logging)
12. [Cost Estimation](#cost-estimation)
13. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

The Graduated Autonomy Engine consists of:

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS Deployment                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │   Backend       │    │   Frontend      │    │   Database  │ │
│  │  (Flask+SocketIO)│───▶│   (React+Vite)  │    │  (SQLite or │ │
│  │                 │    │                 │    │   RDS)      │ │
│  └─────────────────┘    └─────────────────┘    └─────────────┘ │
│         │                 │                      │             │
│         ▼                 ▼                      ▼             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    AWS Services                              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐    │  │
│  │  │   EC2       │  │   S3        │  │   RDS/MySQL      │    │  │
│  │  │  or ECS     │  │   or CloudFront│  │   (Optional)     │    │  │
│  │  │  or Lambda  │  │               │  │                  │    │  │
│  │  └─────────────┘  └─────────────┘  └──────────────────┘    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

### 1. AWS Account
- Sign up for [AWS](https://aws.amazon.com/) (free tier available)
- Set up IAM user with appropriate permissions
- Configure AWS CLI: `aws configure`

### 2. Required Tools
- **AWS CLI**: `pip install awscli` or download from AWS
- **EB CLI** (for Elastic Beanstalk): `pip install awsebcli`
- **Docker** (for ECS/Fargate): Install from [Docker](https://www.docker.com/)
- **Node.js 18+** (for React frontend build)
- **Python 3.8+**

### 3. Domain Name (Optional)
- Purchase domain via Route 53 or use existing domain
- Configure SSL certificate via AWS Certificate Manager

---

## Option 1: AWS Elastic Beanstalk (Simplest)

Elastic Beanstalk is the easiest way to deploy the Flask backend with React frontend.

### Step 1: Prepare Application

#### Build React Frontend
```bash
cd graduated-autonomy/frontend
npm install
npm run build
```

This creates production-ready files in `templates/react/`.

#### Create Deployment Package
```bash
cd graduated-autonomy

# Create requirements.txt for production
pip freeze > requirements-prod.txt

# Create .ebextensions directory for Elastic Beanstalk configuration
mkdir -p .ebextensions
```

#### Create `.ebextensions/01_python.config`
```yaml
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: src/web_app:app
  aws:elasticbeanstalk:container:python:staticfiles:
    /static/: static/
    /templates/react/: templates/react/
  aws:elasticbeanstalk:application:environment:
    FLASK_ENV: production
    ENABLE_AUTONOMY: true
    RESET_LOCAL_DB: false
```

#### Create `.ebextensions/02_nginx.config`
```yaml
files:
  "/etc/nginx/conf.d/proxy.conf":
    mode: "000644"
    owner: root
    group: root
    content: |
      client_max_body_size 20M;
      
  "/etc/nginx/conf.d/socketio.conf":
    mode: "000644"
    owner: root
    group: root
    content: |
      location /socket.io/ {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
      }
```

### Step 2: Create Elastic Beanstalk Application

```bash
# Initialize EB CLI
eb init -p python-3.8 graduated-autonomy-engine --region us-east-1

# Select codecommit or create new application
# When prompted, select the region closest to you

# Create environment
eb create graduated-autonomy-prod \
  --single \
  --instance-types t3.medium \
  --scale 1 \
  --region us-east-1
```

### Step 3: Deploy

```bash
# Zip the application (excluding .venv, node_modules, etc.)
cd graduated-autonomy
zip -r deploy.zip . \
  -x "*.venv*" \
  -x "node_modules/*" \
  -x "frontend/node_modules/*" \
  -x ".git/*" \
  -x "__pycache__/*" \
  -x "*.pyc" \
  -x "data/*" \
  -x "audit.log"

# Deploy
eb deploy graduated-autonomy-prod --label v1.0 --message "Initial deployment"
```

### Step 4: Configure

- Go to AWS Console > Elastic Beanstalk
- Select your application and environment
- Under Configuration:
  - Set Environment Variables (MISTRAL_API_KEY, etc.)
  - Configure Auto Scaling if needed
  - Set up Load Balancer for production

### Step 5: Enable HTTPS (Optional)

1. Request SSL certificate in AWS Certificate Manager
2. Configure HTTPS listener in Load Balancer
3. Redirect HTTP to HTTPS

---

## Option 2: AWS ECS with Fargate (Containerized)

For containerized deployment with better isolation and scalability.

### Step 1: Create Dockerfile

#### Dockerfile for Backend
```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Build React frontend
WORKDIR /app/frontend
RUN npm install
RUN npm run build

# Set environment variables
ENV FLASK_ENV=production
ENV ENABLE_AUTONOMY=true
ENV PORT=5000

# Expose port
EXPOSE 5000

# Start the application
WORKDIR /app
CMD ["python", "-m", "src.web_app"]
```

#### docker-compose.yml (Optional for local testing)
```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=development
      - ENABLE_AUTONOMY=true
      - MISTRAL_API_KEY=${MISTRAL_API_KEY}
    volumes:
      - .:/app
      - /app/data
      - /app/audit.log
    restart: unless-stopped
```

### Step 2: Build and Push to ECR

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com

# Create ECR repository
aws ecr create-repository --repository-name graduated-autonomy --region us-east-1

# Build Docker image
docker build -t graduated-autonomy:latest .

# Tag and push
docker tag graduated-autonomy:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/graduated-autonomy:latest
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/graduated-autonomy:latest
```

### Step 3: Create ECS Cluster with Fargate

1. **Create Cluster**: AWS Console > ECS > Clusters > Create Cluster > Networking only
2. **Create Task Definition**:
   - Task memory: 4GB
   - Task CPU: 2 vCPU
   - Container: Use ECR image
   - Port mappings: 5000
   - Environment variables: MISTRAL_API_KEY, etc.
3. **Create Service**:
   - Service type: Fargate
   - Number of tasks: 1 (or more for HA)
   - Load balancer type: Application Load Balancer
   - Listener port: 80 (and 443 for HTTPS)

### Step 4: Configure Load Balancer

- Create Application Load Balancer
- Add HTTP listener on port 80
- Add HTTPS listener on port 443 with SSL certificate
- Configure Security Groups to allow traffic

---

## Option 3: AWS EC2 (Manual Deployment)

For full control over the server.

### Step 1: Launch EC2 Instance

```bash
# Launch instance (Ubuntu 22.04 LTS)
aws ec2 run-instances \
  --image-id ami-0abcdef1234567890 \  # Ubuntu 22.04 in your region
  --instance-type t3.medium \
  --key-name my-key-pair \
  --security-group-ids sg-1234567890abcdef0 \
  --subnet-id subnet-1234567890abcdef0 \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=graduated-autonomy}]'
```

### Step 2: Connect and Setup

```bash
# SSH into instance
ssh -i my-key-pair.pem ubuntu@<public-ip>

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y \
  python3-pip \
  python3-dev \
  build-essential \
  nginx \
  nodejs \
  npm \
  git

# Install Python packages
sudo pip3 install virtualenv
```

### Step 3: Deploy Application

```bash
# Clone repository
git clone <your-repo-url> graduated-autonomy
cd graduated-autonomy

# Create virtual environment
python3 -m virtualenv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Build React frontend
cd frontend
npm install
npm run build
cd ..

# Create systemd service
sudo nano /etc/systemd/system/graduated-autonomy.service
```

#### Systemd Service File
```ini
[Unit]
Description=Graduated Autonomy Engine
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/graduated-autonomy
Environment="PATH=/home/ubuntu/graduated-autonomy/venv/bin"
Environment="FLASK_ENV=production"
Environment="ENABLE_AUTONOMY=true"
ExecStart=/home/ubuntu/graduated-autonomy/venv/bin/python -m src.web_app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable graduated-autonomy
sudo systemctl start graduated-autonomy

# Check status
sudo systemctl status graduated-autonomy
```

### Step 4: Configure Nginx as Reverse Proxy

```bash
sudo nano /etc/nginx/sites-available/graduated-autonomy
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /socket.io/ {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/graduated-autonomy /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 5: Enable HTTPS with Let's Encrypt

```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renew
sudo certbot renew --dry-run
```

---

## Option 4: Serverless with AWS Lambda (API Only)

For serverless deployment of the backend API only.

### Step 1: Package for Lambda

```bash
# Install dependencies
pip install -r requirements.txt -t ./lambda_package

# Copy application code
cp -r src/* lambda_package/
cp lambda_handler.py lambda_package/

# Create deployment package
cd lambda_package
zip -r ../lambda_deployment.zip .
cd ..
```

### Step 2: Create Lambda Function

1. Go to AWS Console > Lambda > Create Function
2. Runtime: Python 3.10
3. Upload deployment package
4. Handler: `lambda_handler.lambda_handler`
5. Timeout: 30 seconds
6. Memory: 1024 MB

### Step 3: Create API Gateway

1. Go to API Gateway > Create API > REST API
2. Create resources for each endpoint (`/api/market`, `/api/financial-analysis`, etc.)
3. Create methods (GET, POST) for each resource
4. Integration type: Lambda Function
5. Deploy API to a stage (e.g., `prod`)

### Step 4: Configure Lambda for Socket.IO

Note: Socket.IO requires persistent connections, which is challenging with Lambda. Consider:
- Using API Gateway WebSocket API
- Or using Elastic Beanstalk/ECS for Socket.IO

### Step 5: Frontend Deployment

Deploy React frontend to S3 + CloudFront (see below).

---

## Frontend Deployment Options

### Option A: S3 + CloudFront (Static Hosting)

#### Step 1: Build React Frontend
```bash
cd frontend
npm run build
```

#### Step 2: Upload to S3
```bash
# Create S3 bucket
aws s3 mb s3://graduated-autonomy-frontend --region us-east-1

# Enable static website hosting
aws s3 website s3://graduated-autonomy-frontend \
  --index-document index.html \
  --error-document index.html

# Upload files
aws s3 sync templates/react/ s3://graduated-autonomy-frontend/ \
  --delete

# Set bucket policy for public access
cat > bucket-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::graduated-autonomy-frontend/*"
    }
  ]
}
EOF

aws s3 bucket-policy s3://graduated-autonomy-frontend bucket-policy.json
```

#### Step 3: Configure CloudFront

1. Go to CloudFront > Create Distribution
2. Origin Domain: `graduated-autonomy-frontend.s3-website-us-east-1.amazonaws.com`
3. Default Cache Behavior:
   - Viewer Protocol Policy: Redirect HTTP to HTTPS
   - Allowed HTTP Methods: GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE
4. Alternate Domain Name: your-domain.com (optional)
5. SSL Certificate: Select from ACM
6. Default Root Object: index.html
7. Error Pages: Create custom error responses for 403, 404 to return index.html

### Option B: Serve with Flask Backend

If using Elastic Beanstalk, ECS, or EC2, the React frontend is already built into the `templates/react/` directory and served by Flask automatically (as configured in web_app.py).

---

## Database Configuration

### Option 1: SQLite (Single Instance)

SQLite is suitable for development and single-instance deployments:
- File stored at `data/local.db`
- Automatically created by the application
- No additional configuration needed

**Limitations**:
- Not suitable for multi-instance deployments
- File-based, so only one instance can write at a time

### Option 2: Amazon RDS (Multi-Instance)

For production with multiple instances:

#### Step 1: Create RDS Instance

1. Go to RDS > Create Database
2. Engine: PostgreSQL or MySQL
3. Template: Free tier or Dev/Test
4. DB Instance Size: db.t3.micro (free tier eligible)
5. Storage: 20GB
6. Connectivity: Public access (for testing) or VPC only
7. Database authentication: Password
8. Initial database name: `graduated_autonomy`

#### Step 2: Configure Application

Update `src/storage/sqlite_storage.py` to use PostgreSQL/MySQL instead of SQLite, or create a new storage adapter.

#### Step 3: Set Environment Variables

```bash
# For Elastic Beanstalk
eb setenv DB_HOST=your-rds-endpoint.rds.amazonaws.com \
  DB_PORT=5432 \
  DB_NAME=graduated_autonomy \
  DB_USER=admin \
  DB_PASSWORD=your-password
```

### Option 3: DynamoDB (Serverless)

For serverless deployments:

#### Step 1: Create DynamoDB Tables

```bash
# Create tables for actions, confirmations, reviews, audit logs
aws dynamodb create-table \
  --table-name GraduatedAutonomy-Actions \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

aws dynamodb create-table \
  --table-name GraduatedAutonomy-Confirmations \
  --attribute-definitions AttributeName=action_id,AttributeType=S \
  --key-schema AttributeName=action_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

aws dynamodb create-table \
  --table-name GraduatedAutonomy-Reviews \
  --attribute-definitions AttributeName=action_id,AttributeType=S \
  --key-schema AttributeName=action_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

aws dynamodb create-table \
  --table-name GraduatedAutonomy-AuditLogs \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

#### Step 2: Update Storage Adapter

Create a new storage adapter in `src/storage/dynamodb_storage.py`.

---

## Environment Variables

Set these environment variables based on your deployment:

### Required
```bash
# API Keys
MISTRAL_API_KEY=your_mistral_api_key_here

# Application Settings
FLASK_ENV=production
ENABLE_AUTONOMY=true
RESET_LOCAL_DB=false
AUTONOMY_INTERVAL=30
```

### Optional
```bash
# TradingAgents Settings
TRADINGAGENTS_MAX_DEBATE_ROUNDS=1
TRADINGAGENTS_MAX_RISK_ROUNDS=1
TRADINGAGENTS_LLM_PROVIDER=mistral

# Model Settings
MISTRAL_DEEP_THINK_MODEL=mistral-small-latest
MISTRAL_QUICK_THINK_MODEL=mistral-small-latest

# Database (if using RDS)
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_PORT=5432
DB_NAME=graduated_autonomy
DB_USER=admin
DB_PASSWORD=your-password

# Redis (for caching, optional)
REDIS_HOST=your-redis-endpoint.cache.amazonaws.com
REDIS_PORT=6379
```

### For Development
```bash
FLASK_ENV=development
ENABLE_AUTONOMY=false
```

---

## Security Considerations

### 1. IAM Permissions

Create an IAM policy with least privilege:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2. Security Groups

- Allow inbound traffic only on ports 80 (HTTP), 443 (HTTPS)
- For EC2/ECS, allow port 5000 only from Load Balancer or within VPC
- Restrict SSH access to your IP address only

### 3. Secrets Management

**Never hardcode secrets!** Use:

1. **AWS Systems Manager Parameter Store** (Free)
   ```bash
   # Store secret
aws ssm put-parameter \
     --name /graduated-autonomy/MISTRAL_API_KEY \
     --value your-api-key \
     --type SecureString \
     --region us-east-1
   
   # Retrieve in application
   import boto3
   ssm = boto3.client('ssm')
   response = ssm.get_parameter(Name='/graduated-autonomy/MISTRAL_API_KEY', WithDecryption=True)
   ```

2. **AWS Secrets Manager** (Paid, more features)

3. **Environment Variables** (via Elastic Beanstalk, ECS, etc.)

### 4. API Security

- Enable CORS only for your domains
- Rate limit API endpoints (use Flask-Limiter)
- Validate all inputs
- Use HTTPS everywhere

---

## Monitoring and Logging

### 1. CloudWatch Logs

All AWS services can send logs to CloudWatch:
- Elastic Beanstalk: Automatic
- ECS: Configure in task definition
- EC2: Install CloudWatch Agent
- Lambda: Automatic

### 2. Custom Metrics

Track key metrics:
- Number of trades executed
- Risk score distribution
- Autonomy level decisions
- API response times
- Error rates

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

cloudwatch.put_metric_data(
    Namespace='GraduatedAutonomy',
    MetricData=[
        {
            'MetricName': 'TradesExecuted',
            'Dimensions': [
                {'Name': 'Environment', 'Value': 'Production'},
                {'Name': 'AutonomyLevel', 'Value': 'autonomous'}
            ],
            'Value': 1.0,
            'Unit': 'Count'
        }
    ]
)
```

### 3. Alarms

Create CloudWatch alarms for:
- High error rates
- CPU usage > 80%
- Memory usage > 80%
- API latency > 1 second

---

## Cost Estimation

### Elastic Beanstalk
| Resource | Cost (us-east-1) | Notes |
|----------|-----------------|-------|
| t3.medium EC2 | ~$0.0416/hour | 2 vCPU, 4GB RAM |
| Application Load Balancer | ~$16/month | For 1M requests |
| EBS Storage | ~$0.10/GB/month | 20GB = $2/month |
| Data Transfer | ~$0.09/GB | Outbound only |
| **Total (approx.)** | **$40-80/month** | Single instance |

### ECS with Fargate
| Resource | Cost (us-east-1) | Notes |
|----------|-----------------|-------|
| Fargate (2 vCPU, 4GB) | ~$0.04048/hour | Per task |
| Application Load Balancer | ~$16/month | For 1M requests |
| ECR Storage | ~$0.10/GB/month | Container images |
| CloudWatch Logs | ~$0.50/GB | Log storage |
| **Total (approx.)** | **$50-100/month** | Single task |

### EC2
| Resource | Cost (us-east-1) | Notes |
|----------|-----------------|-------|
| t3.medium EC2 | ~$0.0416/hour | 2 vCPU, 4GB RAM |
| EBS Storage | ~$0.10/GB/month | 20GB = $2/month |
| Data Transfer | ~$0.09/GB | Outbound only |
| **Total (approx.)** | **$30-60/month** | Single instance |

### Serverless (Lambda + API Gateway)
| Resource | Cost | Notes |
|----------|------|-------|
| Lambda | $0.20 per 1M requests | + $0.0000166667 per GB-second |
| API Gateway | $1.00 per million requests | REST API |
| DynamoDB | $1.25 per million read/write units | Pay-per-request |
| **Total (approx.)** | **$10-50/month** | Low to medium traffic |

### Frontend (S3 + CloudFront)
| Resource | Cost | Notes |
|----------|------|-------|
| S3 Storage | $0.023/GB/month | Static files |
| CloudFront | $0.085/GB | First 1TB/month |
| **Total (approx.)** | **$1-5/month** | Low traffic |

---

## Troubleshooting

### Common Issues

#### 1. Socket.IO Connection Failed

**Problem**: Socket.IO cannot connect to backend.

**Solutions**:
- Check Security Groups: Port 5000 must be open from frontend to backend
- For Elastic Beanstalk: Configure proxy for WebSocket in `.ebextensions`
- For CloudFront: WebSocket support must be enabled
- Check Nginx/ALB configuration for WebSocket proxy

#### 2. React Frontend Not Loading

**Problem**: Blank page or 404 errors.

**Solutions**:
- Verify build succeeded: Check `templates/react/index.html` exists
- Check CloudFront or S3 bucket permissions
- Clear browser cache
- Check paths in vite.config.js (base should be correct)

#### 3. Flask Application Not Starting

**Problem**: Application crashes on startup.

**Solutions**:
- Check logs: `eb logs` (Elastic Beanstalk) or `docker logs` (ECS)
- Verify all environment variables are set
- Check file permissions in deployment package
- Test locally first: `python -m src.web_app`

#### 4. CORS Errors

**Problem**: Cross-Origin Resource Sharing errors in browser.

**Solutions**:
- Configure CORS in Flask:
  ```python
  from flask_cors import CORS
  CORS(app, origins=['https://your-domain.com'])
  ```
- For Elastic Beanstalk: Set CORS headers in Nginx config
- For CloudFront: Configure Allowed HTTP Methods

#### 5. Database Connection Failed

**Problem**: Cannot connect to RDS or DynamoDB.

**Solutions**:
- Check Security Groups: Database port must be accessible
- Verify connection string and credentials
- Check VPC settings (subnets, route tables)
- Test connection locally first

### Debugging Commands

```bash
# Check Elastic Beanstalk logs
eb logs graduated-autonomy-prod --stream

# Check ECS service logs
aws logs tail /ecs/graduated-autonomy --follow

# Check CloudFront distribution
aws cloudfront get-distribution --id YOUR_DISTRIBUTION_ID

# Check S3 bucket contents
aws s3 ls s3://your-bucket-name/ --recursive

# Test Socket.IO connection from browser console
var socket = io('https://your-api-endpoint.com');
socket.on('connect', () => console.log('Connected!'));
socket.on('connect_error', (e) => console.log('Error:', e));
```

---

## Maintenance

### 1. Deployment Updates

```bash
# For Elastic Beanstalk
eb deploy graduated-autonomy-prod --label v1.1 --message "Bug fixes"

# For ECS
# Update task definition with new image
aws ecs update-service \
  --cluster graduated-autonomy \
  --service graduated-autonomy-service \
  --force-new-deployment

# For EC2
# Pull latest code and restart
cd /home/ubuntu/graduated-autonomy
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart graduated-autonomy
```

### 2. Backup

```bash
# Backup database (SQLite)
cp data/local.db data/local.db.backup-$(date +%Y%m%d-%H%M%S)

# Backup RDS
aws rds create-db-snapshot \
  --db-instance-identifier your-db-instance \
  --db-snapshot-identifier graduated-autonomy-backup-$(date +%Y%m%d-%H%M%S)

# Backup S3
aws s3 sync s3://graduated-autonomy-frontend s3://graduated-autonomy-backups/$(date +%Y%m%d-%H%M%S)/frontend/
```

### 3. Monitoring

Set up CloudWatch Dashboards for:
- API request counts and latency
- Error rates
- Resource utilization
- Autonomy decision distribution

---

## Architecture Recommendations

| Deployment Type | Best For | Complexity | Cost |
|----------------|----------|------------|------|
| **Elastic Beanstalk** | Quick deployment, MVP | Low | Medium |
| **ECS with Fargate** | Production, scalable | Medium | Medium |
| **EC2** | Full control, custom config | Medium | Medium |
| **Lambda + API Gateway** | Serverless, low traffic | High | Low |
| **EKS (Kubernetes)** | Large scale, microservices | High | High |

**For most use cases, we recommend Elastic Beanstalk or ECS with Fargate.**

---

## Quick Start Checklist

- [ ] Set up AWS account and IAM user
- [ ] Install AWS CLI and configure
- [ ] Choose deployment option (Elastic Beanstalk recommended)
- [ ] Build React frontend: `cd frontend && npm run build`
- [ ] Create deployment package
- [ ] Set up environment variables
- [ ] Deploy application
- [ ] Configure database
- [ ] Set up monitoring
- [ ] Test all endpoints
- [ ] Enable HTTPS
- [ ] Set up backups

---

## Additional Resources

- [AWS Elastic Beanstalk Documentation](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/Welcome.html)
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/latest/developerguide/Welcome.html)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html)
- [AWS RDS Documentation](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Welcome.html)
- [Flask Deployment Documentation](https://flask.palletsprojects.com/en/2.3.x/deploying/)
- [React Deployment Documentation](https://react.dev/learn/start-a-new-react-project#deployment)

---

## Support

For issues with AWS deployment:
- Check AWS Service Health Dashboard
- Review CloudTrail logs for API errors
- Use AWS Support for critical issues

For application-specific issues:
- Check application logs
- Verify environment configuration
- Test locally before deploying

---

*Last updated: August 19, 2026*
