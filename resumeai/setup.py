from setuptools import setup, find_packages

setup(
    name="resumeai",
    version="7.1.0",
    packages=find_packages(),
    install_requires=[
        "pdfplumber",
        "rapidfuzz",
        "python-dateutil",
        "sentence-transformers>=2.2.0",
        "numpy>=1.24.0",
    ],
)
