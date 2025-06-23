"""Setup configuration for Haven Health Passport LlamaIndex integration."""

from setuptools import find_packages, setup

setup(
    name="haven-llamaindex",
    version="0.1.0",
    description="LlamaIndex integration for Haven Health Passport medical document processing",
    author="Haven Health Team",
    author_email="ai@havenhealthpassport.org",
    packages=find_packages(),
    install_requires=[
        "llama-index>=0.10.12",
        "llama-index-core>=0.10.12",
        "tiktoken>=0.5.2",
        "pandas>=2.1.4",
        "SQLAlchemy[asyncio]>=2.0.25",
        "aiosqlite>=0.19.0",
        "pypdf>=3.17.4",
        "Pillow>=10.2.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-asyncio>=0.21.1",
            "black>=23.12.0",
            "mypy>=1.8.0",
        ]
    },
    python_requires=">=3.11",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Healthcare Industry",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
