from setuptools import setup, find_packages

#with open("README.md", "r", encoding="utf-8") as fh:
    #long_description = fh.read()

setup(
    name="vixiv-sdk",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A Python SDK for the Vixiv API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    install_requires=[
        "requests==2.32.3",
        "python-dotenv==1.1.0",
        "certifi==2025.1.31",
        "charset-normalizer==3.4.1",
        "idna==3.10",
        "numpy==2.2.4",
        "urllib3==2.3.0"
    ],
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
) 