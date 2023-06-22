from distutils.core import setup
import setuptools
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

setup(
    name='potassium',
    packages=['potassium'],
    version='0.1.0',
    license='Apache License 2.0',
    # Give a short description about your library
    description='The potassium package is a flask-like HTTP server for serving large AI models',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Erik Dunteman',
    author_email='erik@banana.dev',
    url='https://www.banana.dev',
    keywords=['Banana server', 'HTTP server', 'Banana', 'Framework'],
    setup_requires=['wheel'],
    install_requires=[
        "Flask",
        "requests",
        "termcolor",
        "redis",
        "boto3"
    ],
    classifiers=[
        # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
)
