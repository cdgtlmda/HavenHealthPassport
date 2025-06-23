# Docker Configuration Guide

## Docker Hub Authentication (Optional)

Docker Hub authentication is only required if you need to:

- Pull private images
- Push images to Docker Hub
- Exceed anonymous pull rate limits

### Setting up Docker Hub Authentication

1. Create a Docker Hub account at https://hub.docker.com

2. Generate a Personal Access Token:

   - Go to Account Settings → Security
   - Click "New Access Token"
   - Give it a descriptive name
   - Select appropriate permissions
   - Copy the token (you won't see it again)

3. Login using the token:

```bash
docker login -u YOUR_USERNAME
# Enter your Personal Access Token when prompted
```

4. Verify authentication:

```bash
docker info | grep Username
```

### Local Docker Registry (Optional)

For development environments that need a local registry:

1. Run a local registry:

```bash
docker run -d -p 5000:5000 --restart=always --name registry registry:2
```

2. Tag and push images:

```bash
docker tag haven-health/backend localhost:5000/haven-health/backend
docker push localhost:5000/haven-health/backend
```

3. Pull from local registry:

```bash
docker pull localhost:5000/haven-health/backend
```

## Current Docker Configuration

- Docker Desktop: 28.1.1
- Docker Compose: v2.35.1
- Allocated RAM: 8GB
- Allocated CPUs: 4
- Auto-start: Configured

## Running Services

All services are defined in `docker-compose.yml`:

- PostgreSQL (port 5432)
- Redis (port 6379)
- MinIO/S3 (ports 9000-9001)
- OpenSearch (port 9200)
- DynamoDB via LocalStack (port 4566)
- LocalStack (port 4566) - AWS service emulation
