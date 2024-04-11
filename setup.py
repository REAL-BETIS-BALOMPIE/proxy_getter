import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="proxy-getter-dander94",
    version="0.2.4",
    author="dander94",
    author_email="",
    description="Simple HTTPS Proxy Getter",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/dander94/proxy-getter",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)