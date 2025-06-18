from setuptools import find_packages, setup


# Read the README file for long description
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()


# Read requirements from requirements.txt
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [
            line.strip() for line in fh if line.strip() and not line.startswith("#")
        ]


setup(
    name="flask-demo",
    version="1.0.0",
    author="Daniel Precioso",
    author_email="daniel.precioso@ie.edu",
    description="Interactive climate data visualization dashboard using Flask and Folium",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/daniprec/flask-demo",
    project_urls={
        "Bug Reports": "https://github.com/daniprec/flask-demo/issues",
        "Source": "https://github.com/daniprec/flask-demo",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.13",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Scientific/Engineering :: Visualization",
        "Framework :: Flask",
    ],
    keywords="flask, climate, data, visualization, folium, geospatial, europe",
    packages=find_packages(),
    python_requires=">=3.13",
    install_requires=read_requirements(),
    include_package_data=True,
    package_data={
        "": ["*.geojson", "*.csv", "*.html", "*.css", "*.js"],
    },
    entry_points={
        "console_scripts": [
            "flask-demo=app:main",
        ],
    },
    zip_safe=False,
    license="MIT",
)
