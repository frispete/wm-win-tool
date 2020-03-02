#!/usr/bin/env python3
# vim:set et ts=8 sw=4:

import re
import sys
import setuptools

pkgname = 'wm-win-tool'
pkgfile = 'wm_win_tool'
pkgfile_py = '{}.py'.format(pkgfile)
description = 'Store and restore desktops, geometries and shaded state of selected X11 windows'
pkgversion = None
author = None
license = None
min_python = (3, 3)


def exit(msg):
    print(msg, file = sys.stderr, flush = True)
    sys.exit(1)


def tag_value(tag, data):
    mo = re.search(r'^__{}__ = \'(.*)\''.format(tag), data, re.MULTILINE)
    if mo:
        return mo.group(1)
    else:
        exit('failed to determine {} from {}'.format(pkgfile))


# check for min. python version
if sys.version_info < min_python:
    exit('{} requires Python {}.{} or later'.format(pkgname, *min_python))


# determine package meta data
with open(pkgfile_py, 'r') as fd:
    data = fd.read()
    license = tag_value('license', data)
    pkgversion = tag_value('version', data)
    author_email = tag_value('author', data)
    mo = re.match(r'(.*?) <(.*)>', author_email)
    if mo:
        author, email = mo.group(1, 2)
    else:
        exit('failed to determine author and email from {}'.format(author_email))


with open('README.md', encoding='utf-8') as readme:
    long_description = readme.read()
    long_description_content_type = 'text/markdown'


setup_params = dict(
    name = pkgname,
    version = pkgversion,
    author = author,
    author_email = email,
    description = description,
    long_description = long_description,
    long_description_content_type = long_description_content_type,
    url = 'https://github.com/frispete/' + pkgname,
    license = license,
    # entry points don't like python modules containing dashes :-(
    py_modules = [pkgfile],
    python_requires = '>=3',
    classifiers = [
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    entry_points = {
        'console_scripts': [
            '{} = {}:main'.format(pkgname, pkgfile),
        ],
    },
)

if __name__ == '__main__':
    setuptools.setup(**setup_params)
