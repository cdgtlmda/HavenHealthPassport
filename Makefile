# Haven Health Passport - Makefile

.PHONY: help install dev test lint format clean docker-up docker-down

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -r requirements.txt
	npm install

dev: ## Install development dependencies
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	npm install
	pre-commit install

test: ## Run all tests
	pytest tests/ -v --cov=src --cov-report=html
	npm test

lint: ## Run linting checks
	black --check src/ tests/
	flake8 src/ tests/
	mypy src/
	npm run lint

format: ## Format code
	black src/ tests/
	isort src/ tests/
	npm run format

clean: ## Clean build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info

docker-up: ## Start local Docker services
	docker-compose up -d

docker-down: ## Stop local Docker services
	docker-compose down

migrate: ## Run database migrations
	alembic upgrade head

verify-aws: ## Verify AWS credentials
	./venv/bin/python scripts/verify-aws.py

bootstrap-cdk: ## Bootstrap AWS CDK
	./venv/bin/python scripts/aws/bootstrap-cdk.py

seed: ## Seed test data
	python scripts/seed_data.py

run-backend: ## Run backend server
	cd backend && uvicorn main:app --reload --port 8000

run-frontend: ## Run frontend development server (demo UI)
	npm run dev

run-web-portal: ## Run web portal (same as run-frontend)
	npm run dev

run-integrated: ## Run backend and web portal together
	./scripts/start-dev.sh

run-mobile-ios: ## Run mobile app on iOS (not implemented yet)
	@echo "Mobile app not implemented yet"

run-mobile-android: ## Run mobile app on Android (not implemented yet)
	@echo "Mobile app not implemented yet"

build: ## Build for production
	docker build -t haven-health-backend ./backend
	npm run build

deploy-dev: ## Deploy to development environment
	cdk deploy HavenHealthDevStack

deploy-prod: ## Deploy to production environment
	cdk deploy HavenHealthProdStack --require-approval broadening

health-check: ## Check system health
	@echo "Checking backend health..."
	@curl -s http://localhost:8000/health | jq .
	@echo "\nChecking frontend health..."
	@curl -s http://localhost:3000/api/health | jq .

logs: ## View application logs
	docker-compose logs -f

test-integration: ## Run integration tests
	pytest tests/integration/ -v

validate-integration: ## Validate all services are integrated properly
	python scripts/validate_integration.py

security-scan: ## Run security scans
	bandit -r src/
	safety check
	npm audit

generate-sdks: ## Generate client SDKs for all supported languages
	@echo "Generating client SDKs..."
	python scripts/generate_sdks.py --language all

generate-sdk-python: ## Generate Python SDK
	@echo "Generating Python SDK..."
	python scripts/generate_sdks.py --language python

generate-sdk-js: ## Generate JavaScript SDK
	@echo "Generating JavaScript SDK..."
	python scripts/generate_sdks.py --language javascript

openapi-spec: ## Export OpenAPI specification
	@echo "Exporting OpenAPI specification..."
	curl -s http://localhost:8000/api/openapi.json | jq '.' > openapi.json

docs-serve: ## Serve documentation locally
	@echo "Serving documentation on http://localhost:8000"
	cd docs && python -m http.server 8000
