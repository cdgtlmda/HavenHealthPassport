# Development Environment Setup Guide

## Missing Requirements Installation

### 1. Install Docker Desktop

Using Homebrew (recommended):
```bash
brew install --cask docker
```

Or download directly:
- Visit https://www.docker.com/products/docker-desktop/
- Download Docker Desktop for Mac
- Install and launch Docker Desktop
- Ensure Docker is running (you'll see the whale icon in the menu bar)

After installation, verify:
```bash
docker --version
docker-compose --version
```

### 2. Install Go Language

Using Homebrew:
```bash
brew install go
```

After installation, verify:
```bash
go version
# Should show: go version go1.24.x darwin/arm64
```

Add to your shell profile (~/.zshrc or ~/.bash_profile):
```bash
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin
```

### 3. Configure AWS Credentials

See [AWS Configuration Guide](./aws-configuration.md) for detailed steps.

Quick setup for development with LocalStack:
```bash
# No real AWS account needed for local development
# LocalStack provides AWS service emulation
docker-compose up localstack
```

### 4. Install VS Code Extensions

#### Automatic Installation
1. Open VS Code
2. Open the project folder
3. VS Code will prompt: "This workspace has extension recommendations"
4. Click "Install All"

#### Manual Installation
Open VS Code and install these essential extensions:

1. **Python Development**:
   - Python (ms-python.python)
   - Pylance (ms-python.vscode-pylance)

2. **AWS Development**:
   - AWS Toolkit (amazonwebservices.aws-toolkit-vscode)

3. **Docker**:
   - Docker (ms-azuretools.vscode-docker)

4. **Code Quality**:
   - ESLint (dbaeumer.vscode-eslint)
   - Prettier (esbenp.prettier-vscode)

## Verification Script

Create and run this verification script:

```bash
#!/bin/bash
echo "Checking development environment..."

# Check Python
if command -v python3 &> /dev/null; then
    echo "✓ Python $(python3 --version)"
else
    echo "✗ Python not found"
fi

# Check Node.js
if command -v node &> /dev/null; then
    echo "✓ Node.js $(node --version)"
else
    echo "✗ Node.js not found"
fi

# Check Docker
if command -v docker &> /dev/null; then
    echo "✓ Docker $(docker --version)"
else
    echo "✗ Docker not found"
fi

# Check Go
if command -v go &> /dev/null; then
    echo "✓ Go $(go version)"
else
    echo "✗ Go not found"
fi

# Check AWS CLI
if command -v aws &> /dev/null; then
    echo "✓ AWS CLI $(aws --version)"
else
    echo "✗ AWS CLI not found"
fi
```

Save as `check-env.sh` and run:
```bash
chmod +x check-env.sh
./check-env.sh
```

## Next Steps

Once all requirements are installed:

1. Start the development environment:
   ```bash
   docker-compose up -d
   ```

2. Activate Python virtual environment:
   ```bash
   source venv/bin/activate
   ```

3. Install Python dependencies:
   ```bash
   pip install -r requirements-core.txt
   ```

4. Run the development server:
   ```bash
   uvicorn src.main:app --reload
   ```

## Troubleshooting

### Docker Issues
- Ensure Docker Desktop is running
- Check Docker daemon: `docker ps`
- Restart Docker Desktop if needed

### Python Issues
- Use Python 3.11+: `python3 --version`
- Recreate venv if needed: `python3 -m venv venv`

### AWS Issues
- For local development, use LocalStack
- Check credentials: `aws configure list`
- Test access: `aws sts get-caller-identity`