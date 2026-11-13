from setuptools import setup, find_packages

setup(
    name="difflens",
    version="1.0.0",
    author="Nikhil Patil",
    author_email="patilnikhil3505@gmail.com",
    description="Autonomous local-first AI code review agent for Git diffs and Pull Requests",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.110.0",
        "uvicorn>=0.28.0",
        "pydantic>=2.0.0",
        "colorama>=0.4.6",
        "tabulate>=0.9.0",
        "requests>=2.28.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "difflens=diff_lens.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Bug Tracking",
    ],
)
