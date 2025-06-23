# Makefile for Haven Health Passport Blockchain Chaincode

.PHONY: all build test clean deploy package lint security-check

# Variables
CHAINCODE_DIRS := health-record cross-border access-control
GO_VERSION := 1.19
DOCKER_IMAGE := golang:$(GO_VERSION)

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
NC := \033[0m # No Color

all: lint test build

# Lint all chaincode
lint:
	@echo "$(GREEN)Linting chaincode...$(NC)"
	@for dir in $(CHAINCODE_DIRS); do \
		echo "$(YELLOW)Linting $$dir...$(NC)"; \
		cd chaincode/$$dir && \
		go fmt ./... && \
		go vet ./... && \
		cd ../..; \
	done
	@echo "$(GREEN)✓ Linting complete$(NC)"

# Run security checks
security-check:
	@echo "$(GREEN)Running security checks...$(NC)"
	@which gosec > /dev/null || (echo "$(RED)gosec not installed. Run: go install github.com/securego/gosec/v2/cmd/gosec@latest$(NC)" && exit 1)
	@for dir in $(CHAINCODE_DIRS); do \
		echo "$(YELLOW)Checking $$dir...$(NC)"; \
		cd chaincode/$$dir && \
		gosec -severity medium ./... || true && \
		cd ../..; \
	done
	@echo "$(GREEN)✓ Security check complete$(NC)"

# Build all chaincode
build:
	@echo "$(GREEN)Building chaincode...$(NC)"
	@for dir in $(CHAINCODE_DIRS); do \
		echo "$(YELLOW)Building $$dir...$(NC)"; \
		cd chaincode/$$dir && \
		GO111MODULE=on go build -o $$dir . && \
		cd ../..; \
	done
	@echo "$(GREEN)✓ Build complete$(NC)"

# Test all chaincode
test:
	@echo "$(GREEN)Testing chaincode...$(NC)"
	@for dir in $(CHAINCODE_DIRS); do \
		echo "$(YELLOW)Testing $$dir...$(NC)"; \
		cd chaincode/$$dir && \
		GO111MODULE=on go test -v -cover ./... && \
		cd ../..; \
	done
	@echo "$(GREEN)✓ Tests complete$(NC)"

# Package chaincode for deployment
package:
	@echo "$(GREEN)Packaging chaincode...$(NC)"
	@mkdir -p build
	@for dir in $(CHAINCODE_DIRS); do \
		echo "$(YELLOW)Packaging $$dir...$(NC)"; \
		cd chaincode/$$dir && \
		GO111MODULE=on go mod vendor && \
		tar -czf ../../build/$$dir.tar.gz . && \
		cd ../..; \
	done
	@echo "$(GREEN)✓ Packaging complete$(NC)"
	@echo "$(YELLOW)Packages created in build/ directory$(NC)"

# Deploy to AWS Managed Blockchain
deploy:
	@echo "$(GREEN)Deploying to AWS Managed Blockchain...$(NC)"
	@./scripts/deploy-chaincode-aws.sh
	@echo "$(GREEN)✓ Deployment initiated$(NC)"

# Clean build artifacts
clean:
	@echo "$(GREEN)Cleaning build artifacts...$(NC)"
	@rm -rf build/
	@for dir in $(CHAINCODE_DIRS); do \
		cd chaincode/$$dir && \
		rm -f $$dir && \
		rm -rf vendor/ && \
		cd ../..; \
	done
	@echo "$(GREEN)✓ Clean complete$(NC)"

# Install development dependencies
install-deps:
	@echo "$(GREEN)Installing development dependencies...$(NC)"
	@go install github.com/securego/gosec/v2/cmd/gosec@latest
	@go install golang.org/x/tools/cmd/goimports@latest
	@go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

# Run chaincode in development mode
dev:
	@echo "$(GREEN)Starting chaincode in development mode...$(NC)"
	@echo "$(YELLOW)Note: This requires a local Fabric network$(NC)"
	@cd chaincode/health-record && \
		CORE_CHAINCODE_ID_NAME=health-record:1.0 \
		CORE_PEER_ADDRESS=localhost:7052 \
		CORE_CHAINCODE_LOGGING_LEVEL=debug \
		go run .

# Generate documentation
docs:
	@echo "$(GREEN)Generating documentation...$(NC)"
	@for dir in $(CHAINCODE_DIRS); do \
		echo "$(YELLOW)Documenting $$dir...$(NC)"; \
		cd chaincode/$$dir && \
		go doc -all . > ../../docs/chaincode-$$dir.txt && \
		cd ../..; \
	done
	@echo "$(GREEN)✓ Documentation generated$(NC)"

# Run integration tests against AWS
integration-test:
	@echo "$(GREEN)Running integration tests...$(NC)"
	@cd ../tests/blockchain && \
		pytest test_integration.py -v
	@echo "$(GREEN)✓ Integration tests complete$(NC)"

# Check chaincode complexity
complexity:
	@echo "$(GREEN)Checking code complexity...$(NC)"
	@which gocyclo > /dev/null || (echo "$(RED)gocyclo not installed. Run: go install github.com/fzipp/gocyclo/cmd/gocyclo@latest$(NC)" && exit 1)
	@for dir in $(CHAINCODE_DIRS); do \
		echo "$(YELLOW)Checking $$dir...$(NC)"; \
		cd chaincode/$$dir && \
		gocyclo -over 10 . && \
		cd ../..; \
	done
	@echo "$(GREEN)✓ Complexity check complete$(NC)"

# Help command
help:
	@echo "$(GREEN)Haven Health Passport Blockchain Makefile$(NC)"
	@echo ""
	@echo "Available commands:"
	@echo "  $(YELLOW)make all$(NC)           - Run lint, test, and build"
	@echo "  $(YELLOW)make lint$(NC)          - Lint all chaincode"
	@echo "  $(YELLOW)make test$(NC)          - Run unit tests"
	@echo "  $(YELLOW)make build$(NC)         - Build chaincode binaries"
	@echo "  $(YELLOW)make package$(NC)       - Package chaincode for deployment"
	@echo "  $(YELLOW)make deploy$(NC)        - Deploy to AWS Managed Blockchain"
	@echo "  $(YELLOW)make security-check$(NC)- Run security analysis"
	@echo "  $(YELLOW)make clean$(NC)         - Clean build artifacts"
	@echo "  $(YELLOW)make install-deps$(NC)  - Install development dependencies"
	@echo "  $(YELLOW)make dev$(NC)           - Run chaincode in development mode"
	@echo "  $(YELLOW)make docs$(NC)          - Generate documentation"
	@echo "  $(YELLOW)make integration-test$(NC) - Run integration tests"
	@echo "  $(YELLOW)make complexity$(NC)    - Check code complexity"
	@echo "  $(YELLOW)make help$(NC)          - Show this help message"
