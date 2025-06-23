#!/bin/bash
# Installation script for LlamaIndex with Python 3.13 compatibility

echo "🚀 Installing LlamaIndex for Haven Health Passport"
echo "================================================"

# Check if we're in the right directory
if [ ! -f "requirements-flexible.txt" ]; then
    echo "❌ Error: requirements-flexible.txt not found"
    echo "Please run this script from the src/ai/llamaindex directory"
    exit 1
fi

# First, upgrade pip to ensure we have the latest resolver
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install core LlamaIndex packages first
echo "📦 Installing core LlamaIndex packages..."
pip install llama-index llama-index-core

# Then install other dependencies
echo "📦 Installing additional dependencies..."
pip install tiktoken openai pandas numpy httpx aiohttp

# Install document processing tools
echo "📦 Installing document processing tools..."
pip install pypdf Pillow

# Install async support
echo "📦 Installing async support..."
pip install "SQLAlchemy[asyncio]>=2.0.0" aiosqlite nest-asyncio

# Optional: Install development tools
read -p "Install development tools? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📦 Installing development tools..."
    pip install pytest pytest-asyncio black mypy
fi

echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Verify installation: python3 verify_installation.py"
echo "2. Run tests: pytest tests/"
