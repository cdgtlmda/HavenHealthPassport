"""Setup script for Haven Health Passport LangChain integration."""

from setuptools import find_packages, setup

# Read requirements
with open("requirements.txt", encoding="utf-8") as f:
    requirements = [
        line.strip() for line in f if line.strip() and not line.startswith("#")
    ]

# Separate dev requirements
dev_requirements = [
    req
    for req in requirements
    if any(pkg in req for pkg in ["pytest", "black", "ruff", "mypy"])
]

core_requirements = [req for req in requirements if req not in dev_requirements]

setup(
    name="haven-health-passport-langchain",
    version="1.0.0",
    description="LangChain integration for Haven Health Passport",
    author="Haven Health Passport Team",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=core_requirements,
    extras_require={"dev": dev_requirements, "all": requirements},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Healthcare Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
