#!/usr/bin/env python
"""Setup configuration for Haven Health Passport."""

from setuptools import find_packages, setup

setup(
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "boto3>=1.29.7",
        "langchain>=0.1.0",
        "langchain-aws>=0.1.3",
        "llama-index>=0.10.2",
        "pydantic>=2.5.0",
        "sqlalchemy>=2.0.23",
        "redis>=5.0.1",
        "fhirclient>=4.1.0",
        "cryptography>=41.0.0",
        "qrcode>=7.4.0",
        "Pillow>=10.0.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "httpx>=0.25.0",
        "python-multipart>=0.0.6",
        "python-jose[cryptography]>=3.3.0",
        "passlib[bcrypt]>=1.7.4",
        "alembic>=1.12.0",
        "asyncpg>=0.29.0",
        "aioboto3>=12.0.0",
        "aioredis>=2.0.1",
        "tenacity>=8.2.0",
        "pydantic-settings>=2.0.0",
        "structlog>=23.2.0",
        "prometheus-client>=0.19.0",
        "opentelemetry-api>=1.21.0",
        "opentelemetry-sdk>=1.21.0",
        "opentelemetry-instrumentation-fastapi>=0.43b0",
    ],
    entry_points={
        "console_scripts": [
            "haven-health=src.main:main",
        ],
    },
)
