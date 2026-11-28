#!/usr/bin/env python3
"""Add the desktop product description translations to the jpackage Debian launcher."""
import hashlib
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from product_descriptions import descriptions

LAUNCHER = Path('opt/kyllene/lib/kyllene-Kyllene.desktop')


def launcher_comments():
    for locale, value in descriptions().items():
        key = f'Comment[{locale}]' if locale != 'en' else 'Comment'
        yield f'{key}={value}'


def localize(package):
    with TemporaryDirectory(dir=package.parent) as scratch:
        working = Path(scratch)
        tree = working / 'unpacked'
        subprocess.run(['dpkg-deb', '--raw-extract', package, tree], check=True)
        launcher = tree / LAUNCHER
        header, separator, actions = launcher.read_text(encoding='utf-8').partition('\n[')
        if not header.startswith('[Desktop Entry]\n'):
            raise ValueError('Expected the jpackage desktop entry')
        header, count = re.subn(r'^Comment=.*$', lambda _: '\n'.join(launcher_comments()),
                                re.sub(r'^Comment\[[^\]\n]+\]=[^\n]*(?:\n|$)', '', header, flags=re.M), flags=re.M)
        if count != 1:
            raise ValueError('Expected one default launcher comment')
        launcher.write_text(header + separator + actions, encoding='utf-8')
        sums = tree / 'DEBIAN/md5sums'
        if sums.is_file():
            digest = hashlib.md5(launcher.read_bytes(), usedforsecurity=False).hexdigest()
            entries = sums.read_text()
            sums.write_text(re.sub(r'^[0-9a-f]{32}(?=  ' + re.escape(LAUNCHER.as_posix()) + r'$)',
                                   digest, entries, flags=re.M))
        rebuilt = working / package.name
        subprocess.run(['dpkg-deb', '--build', '--root-owner-group', tree, rebuilt], check=True)
        rebuilt.replace(package)


if __name__ == '__main__':
    localize(Path(sys.argv[1]).resolve(strict=True))
