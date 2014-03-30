from ez_setup import use_setuptools
use_setuptools()

from setuptools import setup, find_packages

# workaround for http://bugs.python.org/issue15881
try:
    import multiprocessing
except ImportError:
    pass

setup(
    name="tiedye",
    version="dev",
    description="Simple Pythonic Dependency Injection Helper",
    packages=find_packages(),
    author="Martin Atkins",
    author_email="mart@degeneration.co.uk",

    test_suite='nose.collector',

    setup_requires=[
        'nose>=1.0',
        'sphinx>=0.5',
    ],
    tests_require=[
        'nose>=1.0',
        'coverage',
        'mock',
        'pep8',
    ],
    install_requires=[
    ],
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Intended Audience :: Developers",
    ]
)
