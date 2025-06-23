# Docker Registry Setup

## Docker Hub Authentication (Optional)

If you need to push images to Docker Hub:

### 1. Create Docker Hub Account

Visit https://hub.docker.com and create an account if you don't have one.

### 2. Login to Docker Hub

```bash
docker login
```

Enter your Docker Hub username and password when prompted.

### 3. Configure Credentials Storage

Docker stores credentials in:
- macOS: `~/.docker/config.json` (using macOS keychain)
- Linux: `~/.docker/config.json`
- Windows: `%USERPROFILE%\.docker\config.json`

### 4. Tag and Push Images

```bash
# Tag your image
docker tag haven-health-backend:latest yourusername/haven-health-backend:latest

# Push to Docker Hub
docker push yourusername/haven-health-backend:latest
```

## Local Docker Registry (Optional)

For private image storage without external dependencies:

### 1. Start Local Registry

```bash
# Run registry container
docker run -d \
  -p 5000:5000 \
  --restart=always \
  --name registry \
  -v /path/to/registry/data:/var/lib/registry \
  registry:2
```

### 2. Configure Docker to Use Local Registry

Add to Docker daemon config (`~/.docker/daemon.json`):

```json
{
  "insecure-registries": ["localhost:5000"]
}
```

Restart Docker Desktop after making changes.

### 3. Push Images to Local Registry

```bash
# Tag image for local registry
docker tag haven-health-backend:latest localhost:5000/haven-health-backend:latest

# Push to local registry
docker push localhost:5000/haven-health-backend:latest
```

### 4. Pull from Local Registry

```bash
# On another machine or after cleanup
docker pull localhost:5000/haven-health-backend:latest
```

## Registry Security

### Enable TLS for Local Registry

1. Generate certificates:
```bash
mkdir -p certs
openssl req -newkey rsa:4096 -nodes -sha256 -keyout certs/domain.key \
  -x509 -days 365 -out certs/domain.crt
```

2. Run registry with TLS:
```bash
docker run -d \
  --restart=always \
  --name registry \
  -v $(pwd)/certs:/certs \
  -v /path/to/registry/data:/var/lib/registry \
  -e REGISTRY_HTTP_ADDR=0.0.0.0:443 \
  -e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/domain.crt \
  -e REGISTRY_HTTP_TLS_KEY=/certs/domain.key \
  -p 443:443 \
  registry:2
```

### Basic Authentication

1. Create password file:
```bash
mkdir auth
docker run --rm --entrypoint htpasswd registry:2 \
  -Bbn testuser testpassword > auth/htpasswd
```

2. Run registry with auth:
```bash
docker run -d \
  --restart=always \
  --name registry \
  -v $(pwd)/auth:/auth \
  -v $(pwd)/certs:/certs \
  -v /path/to/registry/data:/var/lib/registry \
  -e REGISTRY_AUTH=htpasswd \
  -e REGISTRY_AUTH_HTPASSWD_REALM="Registry Realm" \
  -e REGISTRY_AUTH_HTPASSWD_PATH=/auth/htpasswd \
  -e REGISTRY_HTTP_ADDR=0.0.0.0:443 \
  -e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/domain.crt \
  -e REGISTRY_HTTP_TLS_KEY=/certs/domain.key \
  -p 443:443 \
  registry:2
```

3. Login to secure registry:
```bash
docker login localhost:443
```

## Registry Maintenance

### View Registry Contents

```bash
# List all repositories
curl -X GET https://localhost:5000/v2/_catalog

# List tags for a repository
curl -X GET https://localhost:5000/v2/haven-health-backend/tags/list
```

### Garbage Collection

```bash
# Stop registry
docker stop registry

# Run garbage collection
docker run --rm \
  -v /path/to/registry/data:/var/lib/registry \
  registry:2 bin/registry garbage-collect /etc/docker/registry/config.yml

# Restart registry
docker start registry
```

## Integration with CI/CD

### GitHub Actions

```yaml
name: Build and Push

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Login to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: ${{ secrets.DOCKER_USERNAME }}/haven-health-backend:latest
```

## Best Practices

1. **Use specific tags**: Avoid using only `latest`
2. **Scan images**: Use tools like Trivy or Clair
3. **Limit registry access**: Use authentication and TLS
4. **Regular cleanup**: Remove old unused images
5. **Backup registry data**: Regular backups of registry volumes