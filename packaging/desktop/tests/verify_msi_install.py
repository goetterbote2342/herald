"""Verify Kyllene's MSI description on a disposable Windows CI runner."""
import ctypes
import os
from pathlib import Path
import runpy
import subprocess
import sys
from tempfile import TemporaryDirectory


def run(*args):
    subprocess.run(args, check=True, timeout=180)


def set_culture(culture):
    run('powershell', '-NoProfile', '-Command', f'Set-Culture -CultureInfo "{culture}"')


def build_fixture(root):
    source = root / 'Fixture.java'
    source.write_text('public class Fixture { public static void main(String[] args) {} }', encoding='ascii')
    jars = root / 'input'
    jars.mkdir()
    run('javac', '-d', root, source)
    run('jar', '--create', '--file', jars / 'fixture.jar', '-C', root, 'Fixture.class')
    runtime = root / 'runtime'
    run('jlink', '--add-modules', 'java.base', '--output', runtime)
    run('jpackage', '--type', 'msi', '--name', 'KylleneDescriptionFixture',
        '--input', jars, '--main-jar', 'fixture.jar', '--main-class', 'Fixture',
        '--app-version', '1.0.0', '--description', 'Original fixture description',
        '--win-per-user-install', '--runtime-image', runtime, '--dest', root)
    package, = root.glob('*.msi')
    return package


def registry_description(product):
    import winreg

    key = r'Software\Microsoft\Windows\CurrentVersion\Uninstall' + '\\' + product
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            return winreg.OpenKey(hive, key, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE)
        except FileNotFoundError:
            pass
    raise LookupError(f'Fixture not registered: {product}')


def verify_installed(package, product, expected):
    import winreg

    installed = False
    install_log = package.with_name('install.log')
    repair_log = package.with_name('repair.log')
    try:
        run('msiexec', '/i', package, '/qn', '/norestart', '/l*v', install_log)
        installed = True
        with registry_description(product) as key:
            actual = winreg.QueryValueEx(key, 'Comments')[0]
            assert actual == expected, f'Install wrote {actual!r}, expected {expected!r}'
            # Make sure repair writes the value back, rather than reading an earlier install's value.
            winreg.SetValueEx(key, 'Comments', 0, winreg.REG_SZ, 'Before repair')
        run('msiexec', '/i', package, 'REINSTALL=ALL', 'REINSTALLMODE=amus',
            '/qn', '/norestart', '/l*v', repair_log)
        with registry_description(product) as key:
            actual = winreg.QueryValueEx(key, 'Comments')[0]
            assert actual == expected, f'Repair wrote {actual!r}, expected {expected!r}'
    except (AssertionError, LookupError, OSError, subprocess.SubprocessError):
        for log in (install_log, repair_log):
            if log.exists():
                data = log.read_bytes()
                encoding = 'utf-16' if data.startswith(b'\xff\xfe') else 'mbcs'
                lines = data.decode(encoding, errors='replace').splitlines()
                relevant = [line for line in lines if any(key in line for key in
                            ('UserLanguageID', 'ARPCOMMENTS', 'KylleneDescription', 'Return value 3'))]
                print(log.name, *relevant[-30:], sep='\n', flush=True)
        raise
    finally:
        if installed:
            run('msiexec', '/x', product, '/qn', '/norestart')


def main():
    if sys.platform != 'win32' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('This test installs a fixture and changes culture on a disposable Windows GitHub runner.')
    scripts = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(scripts))
    functions = runpy.run_path(str(scripts / 'localize-msi-description.py'))
    original = subprocess.check_output(
        ['powershell', '-NoProfile', '-Command', '(Get-Culture).Name'], text=True).strip()
    try:
        with TemporaryDirectory() as tmp:
            package = build_fixture(Path(tmp))
            functions['localize'](package)
            with functions['database'](ctypes.WinDLL('msi'), package, 0) as db:
                (product,), = db.execute("SELECT `Value` FROM `Property` WHERE `Property` = 'ProductCode'",
                                         columns=(str,))
            for culture, langid, expected in (
                ('de-DE', 1031, 'Ein Desktop-Client für Hermes Agent.'),
                ('zh-CN', 2052, 'Hermes Agent 的桌面客户端。'),
                ('en-US', 1033, 'A desktop client for Hermes Agent.'),
            ):
                set_culture(culture)
                actual_langid = int(subprocess.check_output([
                    sys.executable, '-c', 'import ctypes; print(ctypes.windll.kernel32.GetUserDefaultLangID() & 65535)'
                ]))
                assert actual_langid == langid, f'{culture} selected Windows language ID {actual_langid}, expected {langid}'
                print(f'Testing native MSI install and repair with {culture}', flush=True)
                verify_installed(package, product, expected)
    finally:
        set_culture(original)


if __name__ == '__main__':
    main()
