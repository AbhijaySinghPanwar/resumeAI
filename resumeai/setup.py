from setuptools import setup, find_packages

setup(
    name="resumeai",
    version="7.0.0",
    packages=find_packages(),
    install_requires=[
        "pdfplumber",
        "rapidfuzz",
        "python-dateutil",
    ],
)
