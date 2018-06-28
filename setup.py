#! /usr/bin/python3

""" Package information for goodmake. """

from setuptools import setup
import pypandoc

from goodmake import theVersion

theReadMe = pypandoc.convert('README.md', 'rst')

setup(
    name='goodmake',
    py_modules=['goodmake'],
    version=theVersion,

    description='A simpler build system',
    long_description=theReadMe,
    long_description_content_type='text/markdown',
    author='Ames Cornish',
    author_email='goodmake@montebellopartners.com',
    license="GPLv3",
    url='https://github.com/AmesCornish/GoodMake',
    keywords=['make', 'build', 'redo'],

    entry_points={
        'console_scripts': [
            'goodmake=goodmake:main',
        ],
    },

    scripts=[
        'scripts/goodmake_clean.sh',
        'scripts/goodmake_lib.sh',
        'scripts/goodmake_every.sh',
    ],
)
