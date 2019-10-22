import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sqlang",
    version="0.2",
    author="Matthew Nicol",
    author_email="matthew.b.nicol@gmail.com",
    description="Generate SQL programmatically with function calls",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/matthewnicol/sqlang",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    python_requires=">=3.6",
)


