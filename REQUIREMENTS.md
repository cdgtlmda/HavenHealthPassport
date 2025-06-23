# Haven Health Passport - Requirements Documentation

## System Requirements

### Operating System

- **macOS**: 10.15+ (Catalina or later)
- **Linux**: Ubuntu 20.04+ or equivalent
- **Windows**: 10/11 with WSL2 recommended

### Software Prerequisites

- **Python**: 3.11 or 3.12 (3.13 not supported due to blockchain dependencies)
- **Node.js**: 18.0.0+ (LTS recommended)
- **npm**: 9.0.0+
- **Git**: Latest version

## Python Dependencies

### Core Application (requirements.txt)

```bash
# Install with: pip install -r requirements.txt
```

**Key Dependencies:**

- `fastapi==0.104.1` - Web framework
- `uvicorn[standard]==0.24.0` - ASGI server
- `boto3==1.29.7` - AWS SDK
- `langchain==0.1.0` - AI/ML framework
- `llama-index>=0.10.0` - Vector database
- `sqlalchemy==2.0.23` - Database ORM
- `redis==5.0.1` - Caching
- `cryptography==41.0.7` - Security

### Additional Python Requirements

- `requirements-dev.txt` - Development tools
- `requirements-test.txt` - Testing frameworks
- `requirements-ml-nlp.txt` - Machine learning models
- `requirements-audio.txt` - Audio processing
- `requirements-medical-models.txt` - Medical AI models

## Node.js Dependencies

### Frontend Framework (package.json)

```bash
# Install with: npm install
```

**Core Dependencies:**

- `react^19.1.0` - UI framework
- `vite^6.3.5` - Build tool
- `typescript^5.8.3` - Type checking
- `tailwindcss^3.4.17` - CSS framework

**UI Components:**

- `@radix-ui/react-*` - UI component library
- `@tanstack/react-query^5.81.2` - Data fetching
- `react-router-dom^7.6.2` - Routing
- `framer-motion^12.18.1` - Animations
- `lucide-react^0.522.0` - Icons

**Build Tools:**

- `@tailwindcss/postcss` - PostCSS plugin
- `autoprefixer^10.4.21` - CSS prefixing
- `@vitejs/plugin-react-swc^3.10.2` - React plugin

## Database Requirements

### PostgreSQL

- **Version**: 13+ recommended
- **Extensions**: Required for FHIR compliance
- **Configuration**: UTF-8 encoding, timezone support

### Redis

- **Version**: 6.0+
- **Purpose**: Session storage, caching
- **Memory**: 1GB+ recommended

## AWS Services (Optional but Recommended)

### Required for Full Functionality

- **AWS Translate** - Multi-language support
- **AWS Transcribe Medical** - Voice transcription
- **AWS Comprehend Medical** - Medical NLP
- **AWS Bedrock** - AI/ML models
- **AWS S3** - Document storage
- **AWS KMS** - Encryption keys

### Configuration

Create `.env.aws` file:

```bash
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
AWS_S3_BUCKET=your-bucket-name
```

## Development Environment Setup

### 1. Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -r requirements-test.txt
```

### 2. Node.js Environment

```bash
# Install Node.js dependencies
npm install

# Verify installation
npm list --depth=0
```

### 3. Database Setup

```bash
# Start PostgreSQL and Redis (Docker)
docker-compose up -d postgres redis

# Run database migrations
alembic upgrade head
```

### 4. Environment Configuration

```bash
# Copy environment template
cp .env.example .env.local

# Edit with your configuration
# Required: DATABASE_URL, REDIS_URL
# Optional: AWS credentials for full functionality
```

## Build and Development

### Development Server

```bash
# Terminal 1: Backend
source venv/bin/activate
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
npm run dev
```

### Production Build

```bash
# Build frontend
npm run build

# Run production server
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

## Testing Requirements

### Python Testing

```bash
# Unit tests
python -m pytest tests/unit/

# Integration tests
python -m pytest tests/integration/

# Coverage testing
python -m pytest --cov=src --cov-report=html
```

### Frontend Testing

```bash
# Unit tests
npm run test

# End-to-end tests
npm run test:e2e

# Coverage
npm run test:coverage
```

## Common Issues and Solutions

### PostCSS Configuration Error

**Error**: `Loading PostCSS Plugin failed: Cannot find module 'autoprefixer'`
**Solution**:

```bash
npm install autoprefixer --save-dev
npm install @tailwindcss/postcss --save-dev
```

### Missing React Dependencies

**Error**: `The following dependencies are imported but could not be resolved`
**Solution**: All required dependencies are in `package.json`. Run:

```bash
npm install
```

### Python Import Errors

**Error**: `ModuleNotFoundError: No module named 'xyz'`
**Solution**:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### AWS Credentials Not Working

**Error**: API returns mock responses instead of real AWS data
**Solution**:

```bash
# Set environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_REGION=us-east-1

# Or create ~/.aws/credentials file
```

## Hardware Recommendations

### Minimum Requirements

- **CPU**: 4 cores, 2.5GHz+
- **RAM**: 8GB
- **Storage**: 20GB free space
- **Network**: Broadband internet for AWS services

### Recommended for Development

- **CPU**: 8 cores, 3.0GHz+
- **RAM**: 16GB+
- **Storage**: 50GB+ SSD
- **Network**: High-speed internet for AI model downloads

## Security Considerations

### Environment Variables

- Never commit `.env*` files to version control
- Use strong, unique passwords for all services
- Rotate AWS credentials regularly

### Database Security

- Use SSL connections for production
- Implement proper backup strategies
- Enable audit logging for compliance

### API Security

- Configure CORS properly for production
- Use HTTPS in production
- Implement rate limiting

## Support and Documentation

- **Main Documentation**: `/docs` directory
- **API Documentation**: Available at `http://localhost:8000/docs` when running
- **Architecture Diagrams**: `/docs/02-architecture/diagrams/`
- **Deployment Guide**: `DEPLOYMENT_CHECKLIST.md`
