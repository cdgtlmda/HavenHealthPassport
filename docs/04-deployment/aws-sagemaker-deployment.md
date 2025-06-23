# AWS SageMaker Cultural Models Deployment Guide

## CRITICAL: Healthcare System for Refugees
This deployment guide is for the Haven Health Passport cultural adaptation models.
These models handle life-critical healthcare communications for displaced populations.

## Prerequisites

1. AWS Account with appropriate permissions
2. SageMaker execution role with access to:
   - S3 buckets for training data and model artifacts
   - CloudWatch for logging and monitoring
   - KMS for encryption
   - VPC access for secure deployment

## Step 1: Configure AWS Credentials

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: us-east-1
# Default output format: json
```

## Step 2: Create SageMaker Execution Role

```bash
# Create the execution role
aws iam create-role \
  --role-name HavenHealthSageMakerRole \
  --assume-role-policy-document file://sagemaker-trust-policy.json

# Attach necessary policies
aws iam attach-role-policy \
  --role-name HavenHealthSageMakerRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess

aws iam attach-role-policy \
  --role-name HavenHealthSageMakerRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

aws iam attach-role-policy \
  --role-name HavenHealthSageMakerRole \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess
```

## Step 3: Create S3 Buckets

```bash
# Training data bucket
aws s3 mb s3://haven-health-training-data --region us-east-1

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket haven-health-training-data \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "aws:kms",
        "KMSMasterKeyID": "alias/haven-health-sagemaker"
      }
    }]
  }'

# Enable versioning for compliance
aws s3api put-bucket-versioning \
  --bucket haven-health-training-data \
  --versioning-configuration Status=Enabled
```

## Step 4: Deploy Cultural Adaptation Models

### Option A: Deploy Pre-trained Models (Recommended for Production)

```bash
# Deploy the cultural pattern classifier
python scripts/deploy_cultural_models.py deploy \
  --model-path s3://haven-health-models/cultural-pattern-classifier/model.tar.gz \
  --inference-instance ml.m5.xlarge \
  --test

# Verify deployment
python scripts/verify_sagemaker_deployment.py \
  --endpoint cultural-pattern-classifier-endpoint
```

### Option B: Train New Models

```bash
# Prepare training data
python scripts/prepare_cultural_training_data.py \
  --input-dir data/cultural_communications \
  --output-bucket haven-health-training-data

# Train the model
python scripts/deploy_cultural_models.py train \
  --training-instance ml.p3.2xlarge \
  --epochs 10 \
  --cultural-region middle_east \
  --target-language ar

# Deploy after training
python scripts/deploy_cultural_models.py deploy \
  --model-path s3://haven-health-training-data/output/model.tar.gz
```

## Step 5: Configure Auto-scaling

```bash
# Register scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace sagemaker \
  --resource-id endpoint/cultural-pattern-classifier-endpoint/variant/AllTraffic \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --min-capacity 2 \
  --max-capacity 10

# Create scaling policy
aws application-autoscaling put-scaling-policy \
  --policy-name cultural-endpoint-scaling \
  --service-namespace sagemaker \
  --resource-id endpoint/cultural-pattern-classifier-endpoint/variant/AllTraffic \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 1000.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "SageMakerVariantInvocationsPerInstance"
    },
    "ScaleInCooldown": 300,
    "ScaleOutCooldown": 60
  }'
```

## Step 6: Set Up Monitoring

```bash
# Create CloudWatch dashboard
aws cloudwatch put-dashboard \
  --dashboard-name HavenHealthCulturalModels \
  --dashboard-body file://cloudwatch-dashboard.json

# Set up SNS notifications
aws sns create-topic --name haven-health-alerts
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:haven-health-alerts \
  --protocol email \
  --notification-endpoint ops@havenhealth.org
```

## Step 7: Test the Deployment

```python
import boto3
import json

# Test the endpoint
runtime = boto3.client('sagemaker-runtime')

test_data = {
    'text': 'Please consult with your family before the procedure.',
    'source_language': 'en',
    'target_language': 'ar',
    'cultural_region': 'middle_east'
}

response = runtime.invoke_endpoint(
    EndpointName='cultural-pattern-classifier-endpoint',
    ContentType='application/json',
    Accept='application/json',
    Body=json.dumps(test_data)
)

result = json.loads(response['Body'].read().decode())
print(f"Cultural sensitivity score: {result['cultural_sensitivity_score']}")
print(f"Detected patterns: {result['detected_patterns']}")
```

## Production Checklist

- [ ] All endpoints deployed and verified
- [ ] Auto-scaling configured with appropriate thresholds
- [ ] CloudWatch alarms set for latency and errors
- [ ] Data capture enabled for model monitoring
- [ ] Backup endpoints deployed in secondary region
- [ ] Load testing completed successfully
- [ ] Cultural sensitivity threshold ≥ 95%
- [ ] PHI handling verified
- [ ] Disaster recovery plan tested
- [ ] On-call rotation established

## Troubleshooting

### High Latency Issues
1. Check CloudWatch metrics for ModelLatency
2. Verify instance type is appropriate for model size
3. Consider enabling Elastic Inference accelerators
4. Check for throttling on S3 or KMS

### Low Cultural Sensitivity Scores
1. Review training data quality
2. Check for data drift in production
3. Analyze failed predictions in CloudWatch logs
4. Consider retraining with more diverse data

### Deployment Failures
1. Verify IAM role has all required permissions
2. Check VPC configuration if using private subnets
3. Ensure S3 model artifacts are accessible
4. Review CloudFormation stack events

## Security Considerations

1. **Encryption**: All data encrypted in transit and at rest
2. **Access Control**: Use IAM roles, not access keys
3. **Network**: Deploy in private VPC subnets
4. **Monitoring**: Enable CloudTrail for all API calls
5. **Compliance**: Regular audits for HIPAA compliance

## Cost Optimization

1. Use spot instances for training (not inference)
2. Enable auto-scaling with conservative thresholds
3. Use S3 Intelligent-Tiering for model artifacts
4. Schedule endpoint shutdown during low-usage hours
5. Monitor costs with AWS Cost Explorer

## Support

For urgent issues affecting patient care:
- On-call Engineer: +1-XXX-XXX-XXXX
- Escalation: engineering-oncall@havenhealth.org
- AWS Support: Premium support ticket with "URGENT-HEALTHCARE" tag
