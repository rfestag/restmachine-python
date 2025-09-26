"""
Setup configuration for the REST Framework package.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="restmachine",
    version="0.1.0",
    author="REST Framework Contributors",
    author_email="contributors@restmachine.example.com",
    description="A lightweight REST framework with dependency injection and webmachine-style state machine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/restmachine",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "validation": ["pydantic>=2.0.0"],
        "dev": [
            "pytest>=6.0",
            "pytest-cov",
            "ruff",
            "mypy",
            "openapi-spec-validator>=0.7.0",
        ],
        "examples": ["uvicorn", "fastapi"],
    },
    entry_points={
        "console_scripts": [
            # Add CLI tools here if needed
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/yourusername/restmachine/issues",
        "Source": "https://github.com/yourusername/restmachine",
        "Documentation": "https://restmachine.readthedocs.io/",
    },
)
