from setuptools import find_packages, setup

setup(
    name="cortex-sdk",
    version="0.1.0",
    description="Cortex MLOps Backbone — Python SDK for pushing features and calling predictions",
    author="Abrar Ahmed",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=[
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
        "kafka-python>=2.0.2",
    ],
    extras_require={
        "async": ["httpx[asyncio]>=0.27.0"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
