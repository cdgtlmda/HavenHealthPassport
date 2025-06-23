# Deployment Architecture with AWS GenAI Services

## Overview

Haven Health Passport uses a multi-region, highly available architecture deployed on AWS with extensive integration of GenAI services including Bedrock, SageMaker, Comprehend Medical, and other AI/ML capabilities.

## Infrastructure Components

### Compute with AI Optimization
- **ECS Fargate**: Serverless containers for microservices with AI-powered auto-scaling
- **Lambda**: Event-driven functions for AI preprocessing and inference
- **EC2 with GPU**: G5 instances for on-premises model inference
- **SageMaker Endpoints**: Managed ML inference infrastructure
- **Batch**: Large-scale AI processing jobs

### Storage for AI/ML
- **S3**: Multi-tier storage for training data and model artifacts
  - Intelligent-Tiering for cost optimization
  - S3 Transfer Acceleration for global model distribution
  - Versioning for model artifact management
- **EFS**: Shared storage for model checkpoints during training
- **FSx for Lustre**: High-performance storage for ML workloads
- **HealthLake**: FHIR data store with built-in NLP

### Networking for AI Services
- **VPC Endpoints**: Private connectivity to AI services
- **PrivateLink**: Secure connection to Bedrock and SageMaker
- **Global Accelerator**: Low-latency access to AI endpoints
- **CloudFront**: CDN for model serving and API caching

### AI/ML Services Configuration

#### Amazon Bedrock Deployment
```yaml
BedrockConfiguration:
  Models:
    - ModelId: anthropic.claude-3-opus-20240229-v1:0
      Provisioned: true
      Throughput: 
        ModelUnits: 10
      UseCase: Medical translation and analysis
    
    - ModelId: anthropic.claude-3-sonnet-20240229-v1:0 
      OnDemand: true
      UseCase: Quick queries and summaries
    
    - ModelId: amazon.titan-embed-text-v1
      OnDemand: true
      UseCase: Document embeddings
    
    - ModelId: stability.stable-diffusion-xl-v1
      OnDemand: true
      UseCase: Medical diagram generation

  Guardrails:
    - Name: medical-content-filter
      ContentFilters:
        - Type: HATE
          Strength: HIGH
        - Type: VIOLENCE  
          Strength: HIGH
      TopicFilters:
        - Name: non-medical-content
          Definition: "Block non-medical conversations"
      WordFilters:
        - ManagedWordLists: [PROFANITY]
    
    - Name: phi-protection
      SensitiveInformationFilters:
        - Type: PII
          Action: BLOCK
        - Type: PHI
          Action: ANONYMIZE

  KnowledgeBases:
    - Name: medical-knowledge
      DataSource: 
        Type: S3
        Uri: s3://haven-medical-knowledge/
      EmbeddingModel: amazon.titan-embed-text-v1
      VectorStore:
        Type: OPENSEARCH_SERVERLESS
        CollectionArn: arn:aws:aoss:region:account:collection/medical-vectors

  Agents:
    - Name: medical-assistant
      Model: anthropic.claude-3-opus
      Instructions: |
        You are a medical assistant for refugee healthcare.
        Always prioritize accuracy and cultural sensitivity.
      ActionGroups:
        - Name: health-records
          Lambda: arn:aws:lambda:region:account:function:health-records-api
        - Name: translation
          Lambda: arn:aws:lambda:region:account:function:translation-api
```

#### Amazon SageMaker Configuration
```yaml
SageMakerDeployment:
  Endpoints:
    - Name: refugee-health-predictor
      Model: custom-xgboost
      InstanceType: ml.m5.xlarge
      InstanceCount: 3
      AutoScaling:
        MinInstances: 2
        MaxInstances: 10
        TargetMetric: InvocationsPerInstance
        TargetValue: 1000
      
    - Name: medical-image-classifier  
      Model: vision-transformer
      InstanceType: ml.g5.2xlarge
      InstanceCount: 2
      ElasticInference:
        Type: ml.eia2.medium
      
    - Name: outbreak-detector
      Model: prophet-timeseries  
      InstanceType: ml.c5.xlarge
      InstanceCount: 2
      MultiModelEndpoint: true
      
  TrainingJobs:
    Schedule: "0 2 * * SUN"  # Weekly retraining
    InstanceType: ml.p3.8xlarge
    SpotInstances: true
    MaxRuntimeInSeconds: 86400
    
  ModelRegistry:
    ApprovalStatus: PendingManualApproval
    ModelPackageGroups:
      - health-prediction-models
      - translation-quality-models
      - fraud-detection-models
      
  Pipelines:
    - Name: model-training-pipeline
      Steps:
        - Processing: Data preparation
        - Training: Model training
        - Evaluation: Model validation
        - RegisterModel: If accuracy > 0.95
        - Deploy: Blue/green deployment
```

#### Amazon Comprehend Medical Configuration
```yaml
ComprehendMedicalSetup:
  CustomEntities:
    - Name: refugee-health-conditions
      EntityTypes:
        - REFUGEE_SPECIFIC_CONDITION
        - TROPICAL_DISEASE
        - MALNUTRITION_INDICATOR
      TrainingData: s3://haven-training/medical-entities/
      
  Ontologies:
    - ICD10CM: enabled
    - RxNorm: enabled  
    - SNOMED_CT: enabled
    
  PHIDetection:
    OutputDataConfig:
      S3Bucket: haven-phi-detection
      S3Key: comprehend-output/
    DataAccessRoleArn: arn:aws:iam::account:role/ComprehendMedicalRole
```

#### Amazon Transcribe Medical Configuration  
```yaml
TranscribeMedicalSetup:
  CustomVocabularies:
    - Name: medical-terms-multilingual
      LanguageCode: en-US
      Phrases:
        - "refugee health"
        - "displacement trauma"
        - "tropical diseases"
      
  StreamingConfiguration:
    EnableChannelIdentification: true
    NumberOfChannels: 2
    ShowSpeakerLabels: true
    VocabularyName: medical-terms-multilingual
    Specialty: PRIMARYCARE
    Type: DICTATION
    
  BatchConfiguration:
    OutputBucketName: haven-transcriptions
    OutputEncryption:
      Type: KMS
      KmsKeyId: arn:aws:kms:region:account:key/transcribe-key
```

### Security for AI Services

#### AI-Specific Security Controls
```yaml
AISecurityControls:
  DataProtection:
    - Service: Macie
      Configuration:
        S3BucketAssociations:
          - haven-training-data
          - haven-model-artifacts
        CustomDataIdentifiers:
          - Pattern: "PATIENT_ID_PATTERN"
          - Pattern: "MEDICAL_RECORD_PATTERN"
    
    - Service: GuardDuty
      Features:
        - S3_DATA_EVENTS: enabled
        - EKS_RUNTIME_MONITORING: enabled
        - LAMBDA_NETWORK_LOGS: enabled
        
  AccessControl:
    - BedrockAccessPolicy:
        Effect: Allow
        Principal: 
          Service: lambda.amazonaws.com
        Action:
          - bedrock:InvokeModel
          - bedrock:InvokeModelWithResponseStream
        Resource: 
          - arn:aws:bedrock:*:*:provisioned-model/*
        Condition:
          StringEquals:
            "aws:RequestedRegion": ["us-east-1", "eu-west-1"]
    
    - SageMakerEndpointPolicy:
        Effect: Allow
        Principal:
          AWS: arn:aws:iam::account:role/ApplicationRole
        Action:
          - sagemaker:InvokeEndpoint
        Resource: arn:aws:sagemaker:*:*:endpoint/*
        Condition:
          IpAddress:
            "aws:SourceIp": ["10.0.0.0/8"]
```

## Deployment Environments with AI Services

### Development
```yaml
Development:
  Region: us-east-1
  AIServices:
    Bedrock:
      Models: [claude-3-sonnet]  # Lower cost model
      OnDemand: true
    SageMaker:
      Endpoints: 
        InstanceType: ml.t3.medium
        SpotInstances: true
    ComprehendMedical:
      BatchJobs: true
      RealTime: false
```

### Staging
```yaml
Staging:
  Region: us-east-1
  MultiAZ: true
  AIServices:
    Bedrock:
      Models: [claude-3-opus, claude-3-sonnet]
      MixedMode: true  # Some provisioned, some on-demand
    SageMaker:
      Endpoints:
        InstanceType: ml.m5.large
        AutoScaling: enabled
      A/BTesting: enabled
    ComprehendMedical:
      BatchJobs: true
      RealTime: true
```

### Production
```yaml
Production:
  Regions: 
    Primary: us-east-1
    Secondary: eu-west-1
    Tertiary: ap-southeast-1
  
  AIServices:
    Bedrock:
      Models: 
        - claude-3-opus: 
            Provisioned: true
            Capacity: 20 units
        - claude-3-sonnet:
            Provisioned: true  
            Capacity: 10 units
      MultiRegion: true
      Failover: automatic
      
    SageMaker:
      Endpoints:
        MultiModel: true
        ElasticInference: true
        EdgeDeployment:
          Regions: [us-east-1, eu-west-1]
          Devices: [medical-tablet, mobile-app]
      
    ComprehendMedical:
      Async: true
      Sync: true
      CustomModels: deployed
      
    HealthLake:
      MultiRegion: true
      CrossRegionReplication: enabled
```

## CI/CD Pipeline for AI/ML

### ML Pipeline Stages
```yaml
MLOps Pipeline:
  Source:
    - CodeCommit: Model code
    - S3: Training data versioning
    - ECR: Container images
    
  Build:
    - CodeBuild:
        Environment: Deep Learning Container
        ComputeType: BUILD_GENERAL1_LARGE
        Steps:
          - Data validation
          - Feature engineering
          - Model training
          - Model evaluation
          
  Test:
    - Model Testing:
        - Unit tests for preprocessing
        - Integration tests for inference
        - Performance benchmarks
        - Bias detection (SageMaker Clarify)
        
  Deploy:
    - SageMaker Model Registry:
        - Approve model version
        - Create model package
        
    - Progressive Rollout:
        - Shadow mode: 1 week
        - Canary: 10% traffic
        - Blue/Green: Full deployment
        
  Monitor:
    - Model Monitor:
        - Data drift detection
        - Model quality metrics
        - Bias drift monitoring
        - Explainability reports
```

### Infrastructure as Code for AI
```yaml
CDK Stacks:
  - AIFoundationStack:
      - Bedrock provisioned capacity
      - SageMaker VPC endpoints  
      - S3 buckets for ML artifacts
      
  - MLPipelineStack:
      - SageMaker Pipelines
      - Step Functions for orchestration
      - EventBridge for scheduling
      
  - InferenceStack:
      - SageMaker endpoints
      - API Gateway integration
      - Lambda functions for preprocessing
      
  - MonitoringStack:
      - CloudWatch dashboards
      - SNS topics for alerts
      - Model Monitor schedules
```

## Scaling Strategy for AI Services

### Horizontal Scaling
```yaml
AutoScaling Configuration:
  SageMakerEndpoints:
    - Metric: InvocationsPerInstance
      Target: 1000
      ScaleOutCooldown: 60
      ScaleInCooldown: 300
      
  LambdaFunctions:
    - ReservedConcurrency: 1000
      ProvisionnedConcurrency: 100
      
  BedrockProvisioned:
    - ModelUnits:
        Min: 5
        Max: 50
        Schedule: 
          Peak: "0 8-18 * * MON-FRI"
          OffPeak: "0 19-7 * * *"
```

### Vertical Scaling
```yaml
Instance Optimization:
  SageMaker:
    - Development: ml.t3.medium
    - Staging: ml.m5.xlarge  
    - Production: ml.c5.4xlarge or ml.g5.2xlarge
    
  Batch Processing:
    - SpotFleet:
        TargetCapacity: 100 vCPUs
        InstanceTypes: [m5.large, m5.xlarge, m5.2xlarge]
        SpotPrice: "0.50"
```

## Disaster Recovery for AI Services

### AI Service Backup Strategy
```yaml
Backup Configuration:
  Models:
    - S3 Versioning: enabled
    - Cross-Region Replication: 3 regions
    - Lifecycle Policy:
        - Current: Immediate
        - Previous: 30 days
        - Archive: 1 year
        
  Training Data:
    - S3 Backup: Daily snapshots
    - Glacier Deep Archive: After 90 days
    
  Endpoints:
    - Configuration Backup: Daily
    - Automatic Failover: < 5 minutes
```

### Recovery Procedures
```yaml
AIServiceRecovery:
  RPO: 1 hour
  RTO: 2 hours
  
  Procedures:
    - Model Artifacts: Restore from S3
    - Endpoints: CloudFormation recreation
    - Training Jobs: Resume from checkpoints
    - Bedrock: Automatic multi-region failover
```

## Monitoring and Alerting for AI Services

### AI-Specific Metrics
```yaml
CloudWatch Metrics:
  Custom Metrics:
    - ModelAccuracy
    - InferenceLatency  
    - TokenUsage (Bedrock)
    - DataDrift
    - BiasScore
    
  Alarms:
    - ModelAccuracy < 0.90: Critical
    - InferenceLatency > 500ms: Warning
    - TokenUsage > 80% quota: Warning
    - DataDrift > threshold: Critical
```

### AI Operations Dashboard
```yaml
QuickSight Dashboard:
  Panels:
    - Model Performance Trends
    - Inference Request Volume
    - Cost per Inference
    - Data Quality Metrics
    - User Satisfaction Scores
    
  ML Insights:
    - Anomaly Detection: Automated
    - Forecasting: 7-day prediction
    - What-if Analysis: Cost optimization
```

## Cost Optimization for AI Services

### AI Cost Management
```yaml
Cost Optimization Strategies:
  Bedrock:
    - Use Provisioned for predictable workloads
    - On-demand for spikes
    - Model selection based on task complexity
    
  SageMaker:
    - Spot instances for training (70% savings)
    - Multi-model endpoints
    - Automatic model unloading
    - Serverless inference for low traffic
    
  Comprehend Medical:
    - Batch processing for non-urgent
    - Result caching in DynamoDB
    
  Storage:
    - Intelligent-Tiering for ML artifacts
    - Lifecycle policies for old models
    - Compression for training data
```

## Security Hardening for AI

### AI-Specific Security Measures
```yaml
Security Controls:
  Model Security:
    - Encrypted model artifacts
    - Signed model packages
    - Access logging for all invocations
    
  Data Privacy:
    - Differential privacy in training
    - Federated learning options
    - On-premises inference for sensitive data
    
  Compliance:
    - HIPAA compliance for all AI services
    - Model cards for transparency
    - Audit trails for AI decisions
    
  Network Security:
    - VPC endpoints for all AI services
    - Private subnets for training
    - WAF rules for inference APIs
```

## Performance Benchmarks

| AI Service | Operation | Target Latency | Throughput |
|------------|-----------|----------------|------------|
| Bedrock Claude 3 | Inference | < 2s | 1000 req/min |
| SageMaker Endpoint | Prediction | < 100ms | 5000 req/min |
| Comprehend Medical | Entity Extraction | < 500ms | 2000 docs/min |
| Transcribe Medical | Streaming | Real-time | 100 concurrent |
| HealthLake | FHIR Query | < 200ms | 10000 req/min |
| Translation Pipeline | Full Document | < 5s | 500 docs/min |