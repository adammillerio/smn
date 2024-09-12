#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="smn-cli",
    version="0.0.1",
    license="MIT",
    description="a macro command runner",
    author="Adam Miller",
    author_email="miller@adammiller.io",
    url="https://github.com/adammillerio/smn",
    download_url="https://github.com/adammillerio/smn/archive/v0.0.1.tar.gz",
    keywords=[],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3 :: Only",
    ],
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click",
        "click_tree",
        "fabric2",
    ],
    extras_require={"dev": ["ruff", "pyre-check"]},
    entry_points="""
    [console_scripts]
    smn=smn.cli:smn
  """,
)
