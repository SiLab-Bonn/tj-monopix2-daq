#!/usr/bin/env python

from setuptools import setup
from setuptools import find_packages

import tjmonopix2

version = tjmonopix2.__version__

author = 'Christian Bespin, Toko Hirono'
author_email = ''

# Requirements
install_requires = ['basil-daq>=3.0.0', 'coloredlogs', 'numba', 'numpy', 'matplotlib', 'tables', 'tqdm']

setup(
    name='tjmonopix2',
    version=version,
    description='DAQ for TJ-Monopix2 prototype',
    url='https://github.com/SiLab-Bonn/tj-monopix2-daq',
    license='',
    long_description='',
    author=author,
    maintainer=author,
    author_email=author_email,
    maintainer_email=author_email,
    install_requires=install_requires,
    python_requires=">=3.0",
    packages=find_packages(),
    include_package_data=True,
    platforms='any',
)
