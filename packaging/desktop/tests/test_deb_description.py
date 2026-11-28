import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'localize-deb-description.py'
LAUNCHER = 'opt/kyllene/lib/kyllene-Kyllene.desktop'


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


class DebDescriptionTest(unittest.TestCase):
    def test_replaces_the_launcher_description_and_keeps_package_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            control = source / 'DEBIAN'
            control.mkdir(parents=True)
            control_text = ('Package: kyllene\nVersion: 0.20.0\nArchitecture: amd64\n'
                            'Maintainer: Kyllene <team@example.com>\nDescription: Kyllene for Hermes Agent\n')
            (control / 'control').write_text(control_text)
            launcher = source / LAUNCHER
            launcher.parent.mkdir(parents=True)
            launcher.write_text('[Desktop Entry]\nName=Kyllene\nComment=English\nExec=/opt/kyllene/bin/Kyllene\nComment[de]=Old German comment')
            (control / 'md5sums').write_text('00000000000000000000000000000000  ' + LAUNCHER + '\n')
            package = root / 'kyllene.deb'
            run('dpkg-deb', '--build', '--root-owner-group', source, package)

            for _ in range(2):
                run(sys.executable, SCRIPT, package)
            installed = root / 'extracted'
            run('dpkg-deb', '--raw-extract', package, installed)
            localized = (installed / LAUNCHER).read_text(encoding='utf-8')
            self.assertEqual([line for line in localized.splitlines() if not line.startswith('Comment')],
                             ['[Desktop Entry]', 'Name=Kyllene', 'Exec=/opt/kyllene/bin/Kyllene'])
            self.assertEqual((installed / 'DEBIAN/control').read_text(), control_text)
            self.assertEqual((installed / 'DEBIAN/md5sums').read_text(),
                             hashlib.md5(localized.encode()).hexdigest() + '  ' + LAUNCHER + '\n')
            comments = [line for line in localized.splitlines() if line.startswith('Comment')]
            self.assertEqual(len(comments), 7)
            self.assertIn('Comment=A desktop client for Hermes Agent.', comments)
            self.assertIn('Comment[pt_BR]=Um cliente de desktop para o Hermes Agent.', comments)
            self.assertIn('Comment[zh_CN]=Hermes Agent 的桌面客户端。', comments)


if __name__ == '__main__':
    unittest.main()
