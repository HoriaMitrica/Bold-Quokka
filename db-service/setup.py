from setuptools import setup, find_packages

# Read the service dependencies
with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="db-service",
    version="0.1.0",
    packages=find_packages(where="app"),
    package_dir={"": "app"},
    install_requires=requirements,
    # Uncomment and adjust entry_points if you want a console script
    # entry_points={
    #     "console_scripts": [
    #         "db-service=db-service.app.main:main",
    #     ],
    # },
)

