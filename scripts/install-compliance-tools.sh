#!/bin/bash
# Install all required compliance checking tools

echo "Installing compliance checking tools..."

# Activate virtual environment
source /Users/cadenceapeiron/Documents/HavenHealthPassport/venv/bin/activate

# Install all required tools
pip install flake8 flake8-docstrings flake8-bugbear
pip install pylint
pip install mypy types-requests types-PyYAML
pip install pytest pytest-cov pytest-asyncio
pip install bandit[toml]
pip install radon
pip install black isort  # Already installed but ensuring latest

echo "All tools installed successfully!"
echo "You can now run the compliance check scripts."
