# Deployment Guide for Offline Functionality

## Overview

This guide covers the deployment process for Haven Health Passport's offline functionality across different platforms and environments. It includes pre-deployment checks, deployment procedures, and post-deployment verification.

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Mobile Deployment](#mobile-deployment)
3. [Web Deployment](#web-deployment)
4. [Backend Deployment](#backend-deployment)
5. [Infrastructure Setup](#infrastructure-setup)
6. [Monitoring Setup](#monitoring-setup)
7. [Rollback Procedures](#rollback-procedures)
8. [Post-Deployment Verification](#post-deployment-verification)

## Pre-Deployment Checklist

### Code Readiness
- [ ] All offline features tested
- [ ] Sync functionality verified
- [ ] Conflict resolution tested
- [ ] Performance benchmarks met
- [ ] Security audit completed
- [ ] Code review approved
- [ ] Documentation updated

### Environment Preparation
- [ ] Database migrations ready
- [ ] API endpoints deployed
- [ ] CDN cache cleared
- [ ] SSL certificates valid
- [ ] Backup procedures tested
- [ ] Monitoring alerts configured
- [ ] Rollback plan documented

### Testing Verification
- [ ] Unit tests passing (100% coverage)
- [ ] Integration tests passing
- [ ] E2E tests passing
- [ ] Performance tests passing
- [ ] Security tests passing
- [ ] Offline scenarios tested
- [ ] Cross-platform compatibility verified

## Mobile Deployment

### iOS Deployment

#### 1. Build Configuration
```bash
# Update build configuration
cd ios
pod install --repo-update

# Configure offline capabilities
# In Info.plist, add:
<key>UIBackgroundModes</key>
<array>
    <string>fetch</string>
    <string>remote-notification</string>
    <string>processing</string>
</array>

<key>BGTaskSchedulerPermittedIdentifiers</key>
<array>
    <string>org.havenhealthpassport.sync</string>
</array>
```

#### 2. Build Process
```bash
# Clean build
xcodebuild clean -workspace HavenHealthPassport.xcworkspace -scheme HavenHealthPassport

# Archive for release
xcodebuild archive \
  -workspace HavenHealthPassport.xcworkspace \
  -scheme HavenHealthPassport \
  -configuration Release \
  -archivePath ./build/HavenHealthPassport.xcarchive

# Export IPA
xcodebuild -exportArchive \
  -archivePath ./build/HavenHealthPassport.xcarchive \
  -exportPath ./build \
  -exportOptionsPlist ./exportOptions.plist
```

#### 3. TestFlight Deployment
```bash
# Upload to TestFlight
xcrun altool --upload-app \
  --type ios \
  --file ./build/HavenHealthPassport.ipa \
  --username $APPLE_ID \
  --password $APP_SPECIFIC_PASSWORD
```

### Android Deployment

#### 1. Build Configuration
```gradle
// android/app/build.gradle
android {
    defaultConfig {
        // Enable multidex for offline libraries
        multiDexEnabled true
        
        // Configure offline sync
        manifestPlaceholders = [
            syncAdapterService: "org.havenhealthpassport.sync.SyncAdapterService",
            syncAccountType: "org.havenhealthpassport.account"
        ]
    }
    
    buildTypes {
        release {
            minifyEnabled true
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
            
            // Offline-specific ProGuard rules
            proguardFiles 'offline-proguard-rules.pro'
        }
    }
}

dependencies {
    // Offline dependencies
    implementation 'androidx.work:work-runtime:2.8.1'
    implementation 'net.zetetic:android-database-sqlcipher:4.5.0'
}
```

#### 2. Build Process
```bash
# Clean build
cd android
./gradlew clean

# Build release APK
./gradlew assembleRelease

# Build release bundle
./gradlew bundleRelease

# Sign the bundle
jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 \
  -keystore release.keystore \
  app/build/outputs/bundle/release/app-release.aab \
  release-key
```

#### 3. Play Store Deployment
```bash
# Upload to Play Console using fastlane
fastlane android deploy_to_play_store
```

### Cross-Platform Configuration

```javascript
// Configure react-native-config for offline features
// .env.production
ENABLE_OFFLINE_MODE=true
SYNC_INTERVAL=300000
MAX_OFFLINE_DAYS=30
CONFLICT_RESOLUTION_STRATEGY=auto
ENABLE_BACKGROUND_SYNC=true
```

## Web Deployment

### Progressive Web App Setup

#### 1. Build Configuration
```javascript
// webpack.prod.config.js
const WorkboxPlugin = require('workbox-webpack-plugin');
const WebpackPwaManifest = require('webpack-pwa-manifest');

module.exports = {
  plugins: [
    new WorkboxPlugin.GenerateSW({
      clientsClaim: true,
      skipWaiting: true,
      maximumFileSizeToCacheInBytes: 10 * 1024 * 1024, // 10MB
      runtimeCaching: [{
        urlPattern: /^https:\/\/api\.havenhealthpassport\.org\//,
        handler: 'NetworkFirst',
        options: {
          cacheName: 'api-cache',
          expiration: {
            maxEntries: 100,
            maxAgeSeconds: 86400 // 1 day
          }
        }
      }]
    }),
    
    new WebpackPwaManifest({
      name: 'Haven Health Passport',
      short_name: 'Haven Health',
      description: 'Secure health records for refugees',
      background_color: '#ffffff',
      theme_color: '#1976d2',
      start_url: '/',
      display: 'standalone',
      icons: [
        {
          src: path.resolve('src/assets/icon.png'),
          sizes: [96, 128, 192, 256, 384, 512]
        }
      ]
    })
  ]
};
```

#### 2. Build Process
```bash
# Install dependencies
npm ci

# Run production build
npm run build:prod

# Optimize assets
npm run optimize:images
npm run optimize:fonts

# Generate service worker
npm run generate:sw

# Create deployment bundle
tar -czf dist.tar.gz dist/
```

#### 3. CDN Deployment
```bash
# Deploy static assets to CDN
aws s3 sync dist/ s3://haven-health-static/ \
  --cache-control "public, max-age=31536000" \
  --exclude "*.html" \
  --exclude "service-worker.js"

# Deploy HTML with shorter cache
aws s3 sync dist/ s3://haven-health-static/ \
  --cache-control "public, max-age=3600" \
  --include "*.html" \
  --include "service-worker.js"

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*"
```

### Server Deployment

```bash
# Deploy to production servers
ansible-playbook -i inventory/production deploy.yml \
  --extra-vars "version=$VERSION"

# Verify deployment
curl -I https://app.havenhealthpassport.org/
```

## Backend Deployment

### API Updates

#### 1. Database Migrations
```bash
# Run migrations
npm run migrate:production

# Verify migrations
npm run migrate:status

# Create backup before major changes
pg_dump -h $DB_HOST -U $DB_USER -d haven_health > backup_$(date +%Y%m%d).sql
```

#### 2. API Deployment
```bash
# Build Docker image
docker build -t havenhealthpassport/api:$VERSION .

# Push to registry
docker push havenhealthpassport/api:$VERSION

# Deploy using Kubernetes
kubectl set image deployment/api api=havenhealthpassport/api:$VERSION

# Wait for rollout
kubectl rollout status deployment/api

# Verify health
kubectl exec -it deployment/api -- npm run health:check
```

### Sync Service Deployment

```yaml
# kubernetes/sync-service.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sync-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: sync-service
  template:
    metadata:
      labels:
        app: sync-service
    spec:
      containers:
      - name: sync-service
        image: havenhealthpassport/sync:$VERSION
        env:
        - name: ENABLE_OFFLINE_SYNC
          value: "true"
        - name: SYNC_BATCH_SIZE
          value: "100"
        - name: CONFLICT_RESOLUTION_ENABLED
          value: "true"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          initialDelaySeconds: 30
          periodSeconds: 10
```

## Infrastructure Setup

### AWS Configuration

#### 1. S3 Buckets
```bash
# Create offline data bucket
aws s3 mb s3://haven-health-offline-data

# Configure bucket policy
aws s3api put-bucket-policy \
  --bucket haven-health-offline-data \
  --policy file://policies/offline-bucket-policy.json

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket haven-health-offline-data \
  --versioning-configuration Status=Enabled
```

#### 2. DynamoDB Tables
```bash
# Create sync metadata table
aws dynamodb create-table \
  --table-name sync-metadata \
  --attribute-definitions \
    AttributeName=deviceId,AttributeType=S \
    AttributeName=timestamp,AttributeType=N \
  --key-schema \
    AttributeName=deviceId,KeyType=HASH \
    AttributeName=timestamp,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST \
  --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES

# Create conflict resolution table
aws dynamodb create-table \
  --table-name sync-conflicts \
  --attribute-definitions \
    AttributeName=conflictId,AttributeType=S \
  --key-schema \
    AttributeName=conflictId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

#### 3. Lambda Functions
```bash
# Deploy sync processor
cd lambda/sync-processor
npm install
zip -r sync-processor.zip .
aws lambda create-function \
  --function-name haven-sync-processor \
  --runtime nodejs18.x \
  --role arn:aws:iam::account-id:role/lambda-sync-role \
  --handler index.handler \
  --zip-file fileb://sync-processor.zip \
  --timeout 300 \
  --memory-size 512

# Configure DynamoDB trigger
aws lambda create-event-source-mapping \
  --function-name haven-sync-processor \
  --event-source-arn arn:aws:dynamodb:region:account:table/sync-metadata/stream/* \
  --starting-position LATEST
```

### Redis Configuration

```bash
# Deploy Redis for sync queue
helm install redis bitnami/redis \
  --set auth.enabled=true \
  --set auth.password=$REDIS_PASSWORD \
  --set replica.replicaCount=2 \
  --set sentinel.enabled=true \
  --set persistence.enabled=true \
  --set persistence.size=10Gi
```

## Monitoring Setup

### CloudWatch Alarms

```bash
# Sync failure alarm
aws cloudwatch put-metric-alarm \
  --alarm-name sync-failure-rate \
  --alarm-description "High sync failure rate" \
  --metric-name SyncFailures \
  --namespace HavenHealth/Sync \
  --statistic Sum \
  --period 300 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --evaluation-periods 2

# Conflict rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name conflict-rate \
  --alarm-description "High conflict rate" \
  --metric-name ConflictCount \
  --namespace HavenHealth/Sync \
  --statistic Average \
  --period 3600 \
  --threshold 50 \
  --comparison-operator GreaterThanThreshold
```

### Datadog Integration

```yaml
# datadog-agent.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: datadog-agent-config
data:
  datadog.yaml: |
    api_key: ${DD_API_KEY}
    logs_enabled: true
    logs_config:
      container_collect_all: true
    process_config:
      enabled: true
    apm_config:
      enabled: true
      apm_non_local_traffic: true
    custom_metrics:
      - name: offline.sync.duration
        query: "avg:haven.sync.duration{*}"
      - name: offline.queue.size
        query: "avg:haven.sync.queue.size{*}"
      - name: offline.conflicts
        query: "sum:haven.sync.conflicts{*}"
```

## Rollback Procedures

### Mobile App Rollback

#### iOS Rollback
```bash
# Revert to previous version in App Store Connect
# 1. Log in to App Store Connect
# 2. Select the app
# 3. Go to "App Store" tab
# 4. Click "Version History"
# 5. Select previous version
# 6. Submit for review with expedited request

# For TestFlight users
# Remove current build
# Add previous stable build
```

#### Android Rollback
```bash
# Revert in Play Console
# 1. Go to Release Management > App releases
# 2. Select the track (Production)
# 3. Create new release
# 4. Add previous APK/Bundle
# 5. Roll out with staged percentage

# Emergency rollback
fastlane android rollback version:$PREVIOUS_VERSION
```

### Web Rollback

```bash
# Revert static files
aws s3 sync s3://haven-health-static-backup/$PREVIOUS_VERSION/ s3://haven-health-static/ \
  --delete

# Clear CDN cache
aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*"

# Update service worker
echo "self.skipWaiting();" > dist/service-worker.js
aws s3 cp dist/service-worker.js s3://haven-health-static/
```

### API Rollback

```bash
# Kubernetes rollback
kubectl rollout undo deployment/api
kubectl rollout undo deployment/sync-service

# Verify rollback
kubectl rollout status deployment/api
kubectl rollout status deployment/sync-service

# Database rollback (if needed)
psql -h $DB_HOST -U $DB_USER -d haven_health < backup_$BACKUP_DATE.sql
```

### Emergency Procedures

```bash
#!/bin/bash
# emergency-rollback.sh

echo "Starting emergency rollback..."

# 1. Stop all sync operations
kubectl scale deployment/sync-service --replicas=0

# 2. Disable offline mode
aws lambda update-function-configuration \
  --function-name haven-sync-processor \
  --environment Variables={OFFLINE_MODE_ENABLED=false}

# 3. Clear sync queues
redis-cli -h $REDIS_HOST FLUSHDB

# 4. Rollback services
kubectl rollout undo deployment/api
kubectl rollout undo deployment/sync-service

# 5. Restore previous version
./deploy.sh $PREVIOUS_VERSION

# 6. Notify team
curl -X POST $SLACK_WEBHOOK \
  -H 'Content-type: application/json' \
  -d '{"text":"Emergency rollback completed to version '$PREVIOUS_VERSION'"}'

echo "Emergency rollback completed"
```

## Post-Deployment Verification

### Automated Tests

```bash
#!/bin/bash
# post-deployment-tests.sh

# 1. Health checks
echo "Running health checks..."
curl -f https://api.havenhealthpassport.org/health || exit 1
curl -f https://app.havenhealthpassport.org/ || exit 1

# 2. Sync functionality test
echo "Testing sync functionality..."
npm run test:e2e:sync -- --env production

# 3. Offline functionality test
echo "Testing offline functionality..."
npm run test:e2e:offline -- --env production

# 4. Performance tests
echo "Running performance tests..."
npm run test:performance -- --env production

# 5. Security scan
echo "Running security scan..."
npm run security:scan -- --env production
```

### Manual Verification Checklist

#### Mobile App
- [ ] App launches without crashes
- [ ] User can log in successfully
- [ ] Offline mode activates when network disconnected
- [ ] Data persists locally when offline
- [ ] Sync resumes when connection restored
- [ ] Conflicts are resolved correctly
- [ ] Background sync works
- [ ] Push notifications received

#### Web Portal
- [ ] PWA installs correctly
- [ ] Service worker activates
- [ ] Offline page displays when disconnected
- [ ] Cached resources load offline
- [ ] Forms work offline
- [ ] Data syncs when reconnected
- [ ] No console errors
- [ ] Performance metrics acceptable

#### Backend
- [ ] All API endpoints responding
- [ ] Sync endpoints handle offline data
- [ ] Conflict resolution working
- [ ] Database queries optimized
- [ ] No error spikes in logs
- [ ] Monitoring alerts configured
- [ ] Backup procedures verified

### Performance Verification

```typescript
// performance-verification.ts
async function verifyPerformance() {
  const metrics = {
    syncDuration: await measureSyncDuration(),
    conflictResolution: await measureConflictResolution(),
    offlineStartup: await measureOfflineStartup(),
    apiLatency: await measureApiLatency()
  };
  
  const thresholds = {
    syncDuration: 30000, // 30 seconds
    conflictResolution: 5000, // 5 seconds
    offlineStartup: 3000, // 3 seconds
    apiLatency: 500 // 500ms
  };
  
  Object.entries(metrics).forEach(([metric, value]) => {
    if (value > thresholds[metric]) {
      console.error(`Performance degradation: ${metric} = ${value}ms`);
      notifyOps({
        alert: 'performance_degradation',
        metric,
        value,
        threshold: thresholds[metric]
      });
    }
  });
}
```

### User Acceptance Testing

```markdown
## UAT Checklist

### Refugee User Flow
1. [ ] Register new account offline
2. [ ] Add health records offline
3. [ ] View records offline
4. [ ] Share records via QR code
5. [ ] Sync when internet available
6. [ ] Receive updates from provider

### Healthcare Provider Flow
1. [ ] Access patient records offline
2. [ ] Update treatment notes offline
3. [ ] Prescribe medications offline
4. [ ] View patient history
5. [ ] Sync updates to central system
6. [ ] Resolve any conflicts

### NGO Administrator Flow
1. [ ] Manage multiple patients offline
2. [ ] Generate reports offline
3. [ ] Export data for analysis
4. [ ] Bulk update records
5. [ ] Monitor sync status
6. [ ] Handle conflict resolution
```

## Deployment Automation

### CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy Offline Features

on:
  push:
    branches: [main]
    paths:
      - 'packages/mobile/**'
      - 'packages/web/**'
      - 'packages/api/**'
      - 'shared/offline/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          npm run test:unit
          npm run test:integration
          npm run test:e2e

  deploy-mobile:
    needs: test
    runs-on: macos-latest
    steps:
      - name: Deploy iOS
        run: fastlane ios release
        env:
          APPLE_ID: ${{ secrets.APPLE_ID }}
          
      - name: Deploy Android
        run: fastlane android release
        env:
          PLAY_STORE_KEY: ${{ secrets.PLAY_STORE_KEY }}

  deploy-web:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Build PWA
        run: npm run build:pwa
        
      - name: Deploy to CDN
        run: npm run deploy:cdn
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}

  deploy-api:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - name: Build Docker image
        run: docker build -t havenhealthpassport/api:${{ github.sha }} .
        
      - name: Deploy to Kubernetes
        run: |
          kubectl set image deployment/api api=havenhealthpassport/api:${{ github.sha }}
          kubectl rollout status deployment/api
```

## Troubleshooting Deployment Issues

### Common Issues

1. **Service Worker Not Updating**
   ```javascript
   // Force service worker update
   navigator.serviceWorker.getRegistration().then(reg => {
     reg.unregister();
     window.location.reload();
   });
   ```

2. **Database Migration Failures**
   ```bash
   # Rollback migration
   npm run migrate:rollback
   
   # Fix issues and retry
   npm run migrate:up
   ```

3. **Sync Service Timeout**
   ```bash
   # Increase timeout
   kubectl patch deployment sync-service -p \
     '{"spec":{"template":{"spec":{"containers":[{"name":"sync-service","livenessProbe":{"timeoutSeconds":30}}]}}}}'
   ```

4. **CDN Cache Issues**
   ```bash
   # Force invalidation
   aws cloudfront create-invalidation \
     --distribution-id $DISTRIBUTION_ID \
     --paths "/*" \
     --caller-reference force-$(date +%s)
   ```

## Success Criteria

### Deployment Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Deployment Duration | < 30 minutes | CI/CD pipeline time |
| Zero Downtime | 100% | Health check monitoring |
| Rollback Time | < 5 minutes | Time to previous version |
| Error Rate | < 0.1% | Post-deployment errors |
| User Impact | None | User reports/feedback |

### Key Performance Indicators

- Sync success rate > 95%
- Offline availability > 99%
- Conflict resolution rate > 90%
- Data consistency > 99.9%
- User satisfaction > 4.5/5

## Documentation

### Deployment Documentation
- [ ] Update deployment runbook
- [ ] Document configuration changes
- [ ] Update architecture diagrams
- [ ] Record lessons learned
- [ ] Update troubleshooting guide
- [ ] Create deployment video guide

### Communication
- [ ] Notify users of new features
- [ ] Update release notes
- [ ] Brief support team
- [ ] Update status page
- [ ] Send deployment report

## Conclusion

This deployment guide ensures reliable and consistent deployment of offline functionality across all platforms. Regular updates to this guide based on deployment experiences will help maintain smooth operations.

Remember:
1. Always test in staging first
2. Have rollback plan ready
3. Monitor closely after deployment
4. Document any issues or improvements
5. Communicate with all stakeholders

For emergency support during deployment, contact the DevOps team via the emergency hotline.