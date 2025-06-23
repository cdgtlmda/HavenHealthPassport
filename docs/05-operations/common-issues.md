# Troubleshooting Guide

## Common Issues and Solutions

### Development Environment

#### Docker Issues

**Problem**: Docker containers won't start
```bash
docker-compose up
# Error: Cannot connect to Docker daemon
```

**Solution**:
1. Ensure Docker Desktop is running
2. Reset Docker to factory defaults if needed
3. Check Docker resource allocation (minimum 8GB RAM)

**Problem**: Port conflicts
```bash
# Error: bind: address already in use
```

**Solution**:
```bash
# Find process using the port
lsof -i :5432  # For PostgreSQL
lsof -i :6379  # For Redis

# Kill the process or change the port in docker-compose.yml
```

#### Python Environment

**Problem**: Module import errors
```python
# ModuleNotFoundError: No module named 'src'
```

**Solution**:
```bash
# Ensure you're in the project root
cd /path/to/HavenHealthPassport

# Activate virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Set PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}"
```

### API Issues

#### Authentication Errors

**Problem**: 401 Unauthorized errors
```json
{"detail": "Invalid authentication credentials"}
```

**Solution**:
1. Check token expiration
2. Verify token format: `Authorization: Bearer <token>`
3. Ensure user has required permissions
4. Check if token is blacklisted

#### Rate Limiting

**Problem**: 429 Too Many Requests
```json
{"detail": "Rate limit exceeded", "retry_after": 60}
```

**Solution**:
1. Check rate limit headers
2. Implement exponential backoff
3. Consider upgrading API tier
4. Use caching to reduce API calls

### Database Issues

#### Connection Errors

**Problem**: Database connection refused
```
psycopg2.OperationalError: could not connect to server
```

**Solution**:
```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check connection string
echo $DATABASE_URL

# Test connection
psql -h localhost -U haven_user -d haven_health
```

#### Migration Errors

**Problem**: Alembic migration conflicts
```
alembic.util.exc.CommandError: Target database is not up to date
```

**Solution**:
```bash
# Check current revision
alembic current

# Upgrade to latest
alembic upgrade head

# If conflicts, downgrade and retry
alembic downgrade -1
alembic upgrade head
```

### AWS Issues

#### Credentials Not Found

**Problem**: AWS credentials error
```
botocore.exceptions.NoCredentialsError
```

**Solution**:
```bash
# Check AWS configuration
aws configure list

# Set credentials
aws configure

# Or use environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
```

#### S3 Access Denied

**Problem**: S3 permission errors
```
botocore.exceptions.ClientError: An error occurred (AccessDenied)
```

**Solution**:
1. Check IAM policy for S3 permissions
2. Verify bucket policy allows access
3. Check if using correct AWS profile
4. Ensure bucket exists and is in correct region

### Performance Issues

#### Slow API Responses

**Symptoms**:
- Response times > 2 seconds
- Timeouts on complex queries

**Solutions**:
1. Add database indexes:
```sql
CREATE INDEX idx_patients_unhcr_id ON patients(unhcr_id);
CREATE INDEX idx_records_patient_id ON health_records(patient_id);
```

2. Enable query caching:
```python
# In Redis
cache_key = f"patient:{patient_id}"
cached = await redis.get(cache_key)
```

3. Optimize N+1 queries:
```python
# Use eager loading
patients = db.query(Patient).options(
    selectinload(Patient.health_records)
).all()
```

#### Memory Leaks

**Symptoms**:
- Increasing memory usage over time
- Container restarts

**Solutions**:
1. Profile memory usage:
```python
import tracemalloc
tracemalloc.start()
# ... code ...
snapshot = tracemalloc.take_snapshot()
```

2. Close resources properly:
```python
async with aiohttp.ClientSession() as session:
    # Use session
    pass  # Auto-closed
```

### Deployment Issues

#### Container Build Failures

**Problem**: Docker build fails
```
docker build -t haven-health .
# Error: failed to solve with frontend
```

**Solution**:
```bash
# Clear Docker cache
docker system prune -a

# Build with no cache
docker build --no-cache -t haven-health .

# Check Dockerfile syntax
docker build --check .
```

#### ECS Task Failures

**Problem**: ECS tasks keep stopping
```
Task stopped: Essential container exited
```

**Solution**:
1. Check CloudWatch logs
2. Verify task IAM role permissions
3. Check health check configuration
4. Ensure sufficient CPU/memory allocated

### Security Issues

#### CORS Errors

**Problem**: CORS policy blocking requests
```
Access-Control-Allow-Origin header missing
```

**Solution**:
```python
# In FastAPI
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.havenhealthpassport.org"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

#### SSL Certificate Errors

**Problem**: SSL verification failed
```
ssl.SSLError: certificate verify failed
```

**Solution**:
1. Update certificates:
```bash
pip install --upgrade certifi
```

2. For development only:
```python
# WARNING: Only for development
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
```

## Getting Help

If issues persist:

1. Check logs:
```bash
# Application logs
docker logs haven-health-backend

# System logs
journalctl -u docker
```

2. Enable debug mode:
```python
# In .env
DEBUG=true
LOG_LEVEL=DEBUG
```

3. Contact support:
- GitHub Issues: https://github.com/haven-health/passport/issues
- Email: support@havenhealthpassport.org
- Slack: #haven-health-support