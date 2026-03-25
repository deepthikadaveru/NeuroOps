from setuptools import setup, find_packages

setup(
    name="neuro-ops",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "requests",
        "pyyaml",
    ],
    entry_points={
        "console_scripts": [
            "neuro-ops=neuroops_core.cli:main",
        ],
    },
    python_requires=">=3.9",
)