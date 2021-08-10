# -*- coding: utf-8 -*-

# SPDX-License-Identifier: MIT
# Copyright © 2021 André Santos

try:
    import regex as re
except ImportError:
    import re
import os
from setuptools import setup, find_packages

SOURCE = os.path.relpath(os.path.join(os.path.dirname(__file__), 'src'))

# Utility function to read the README, etc..
# Used for the long_description and other fields.
def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname)) as f:
        contents = f.read()
    return contents

__version__ ,= re.findall("__version__ = '(.*)'",
    read('src/haroslaunch/__init__.py'))

requirements = [r for r in read('requirements.txt').splitlines() if r]
test_requirements = [r for r in read('test-requirements.txt').splitlines() if r]

setup(
    name             = 'haroslaunch',
    version          = __version__,
    author           = u'André Santos',
    author_email     = 'haros.framework@gmail.com',
    description      = 'ROS launch file parser',
    long_description = read('README.md'),
    long_description_content_type = 'text/markdown',
    license          = 'MIT',
    keywords         = 'haros ros launch-file parser model-extraction',
    url              = 'https://github.com/git-afsantos/haroslaunch',
    packages         = find_packages(SOURCE),
    package_dir      = {'': SOURCE},
    package_data     = {'haroslaunch': []},
    classifiers      = [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Scientific/Engineering',
        'Topic :: Software Development',
        'Topic :: Software Development :: Interpreters',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Text Processing :: Markup :: XML'
    ],
    #entry_points     = {'console_scripts': ['haroslaunch = haroslaunch.main:main']},
    python_requires  = '>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, !=3.5.*',
    install_requires = requirements,
    extras_require   = {
        'test': test_requirements,
    },
    zip_safe         = False
)
