"""Validate reproducible platform archives and run their actual entry points."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]
VARIANT = os.environ.get('SORTER_VARIANT', 'modern' if os.name == 'nt' else 'linux')
EXPECTED_MEMBERS = {
    'windows': {'sort-downloads.bat', 'sort-downloads.ps1', 'sort-downloads-legacy.bat',
                'sort-downloads-legacy.js', 'categories.txt', 'README.md', 'LICENSE'},
    'linux': {'sort-downloads.sh', 'categories.txt', 'README.md', 'LICENSE'},
    'macos': {'Sort Downloads.command', 'categories.txt', 'README.md', 'LICENSE'},
}


class PackageTest(unittest.TestCase):
    def test_unlisted_platform_files_are_excluded(self):
        with tempfile.TemporaryDirectory(prefix='sorter-allowlist-', dir=os.environ.get('TMPDIR')) as temp:
            fixture = Path(temp) / 'repo'
            for folder in ('windows', 'linux', 'macos', 'tools'):
                shutil.copytree(REPO / folder, fixture / folder, ignore=shutil.ignore_patterns('__pycache__'))
            for name in ('README.md', 'LICENSE'):
                shutil.copyfile(REPO / name, fixture / name)
            for platform in ('windows', 'linux', 'macos'):
                (fixture / platform / 'private-backup.txt').write_bytes(b'not a release file')
            result = subprocess.run([sys.executable, str(fixture / 'tools' / 'build_release.py')],
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for platform in ('windows', 'linux', 'macos'):
                with zipfile.ZipFile(fixture / 'dist' / f'downloads-sorter-{platform}-v1.0.0.zip') as z:
                    self.assertEqual(set(z.namelist()), EXPECTED_MEMBERS[platform])

    def test_build_and_run_native_release(self):
        builder = REPO / 'tools' / 'build_release.py'
        self.assertTrue(builder.is_file(), 'Missing release builder')
        with tempfile.TemporaryDirectory(prefix='sorter-package-', dir=os.environ.get('TMPDIR')) as temp:
            temp = Path(temp)
            output = temp / 'dist'
            result = subprocess.run([sys.executable, str(builder), '--output', str(output), '--version', '1.0.0'],
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            archives = sorted(output.glob('*.zip'))
            self.assertEqual(len(archives), 3)
            checksums = {}
            for line in (output / 'SHA256SUMS.txt').read_text().splitlines():
                digest, name = line.split('  ')
                checksums[name] = digest
            self.assertEqual(set(checksums), {p.name for p in archives})
            for archive in archives:
                self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), checksums[archive.name])
                platform = archive.name.split('-')[2]
                with zipfile.ZipFile(archive) as z:
                    self.assertIsNone(z.testzip())
                    self.assertEqual(set(z.namelist()), EXPECTED_MEMBERS[platform])
                    for name in z.namelist():
                        source = REPO / name if name in {'README.md', 'LICENSE'} else REPO / platform / name
                        data = source.read_bytes().replace(b'\r\n', b'\n')
                        if platform == 'windows' and source.suffix in {'.bat', '.ps1', '.js'}:
                            data = data.replace(b'\n', b'\r\n')
                        self.assertEqual(z.read(name), data, name)
                        mode = z.getinfo(name).external_attr >> 16
                        self.assertEqual(mode & 0o777, 0o755 if source.suffix in {'.sh', '.command'} else 0o644)
            platform = 'windows' if VARIANT in {'modern', 'legacy'} else VARIANT
            bundle = temp / 'bundle space & (safe)! %literal%'
            bundle.mkdir()
            with zipfile.ZipFile(output / f'downloads-sorter-{platform}-v1.0.0.zip') as z:
                z.extractall(bundle)
            photo = bundle / 'Фото (пример)! & 1.HEIC'
            photo.write_bytes(b'release-smoke')
            if platform == 'windows':
                launcher = bundle / ('sort-downloads-legacy.bat' if VARIANT == 'legacy' else 'sort-downloads.bat')
                # An explicit command string is required for cmd /s's outer-quote rules.
                command = f'cmd.exe /d /s /c ""{launcher}" --apply"'
            else:
                launcher = bundle / ('sort-downloads.sh' if platform == 'linux' else 'Sort Downloads.command')
                interpreter = '/bin/bash' if sys.platform == 'darwin' else shutil.which('bash')
                command = [interpreter, launcher.as_posix(), '--apply']
            result = subprocess.run(command, cwd=temp, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((bundle / 'photos' / photo.name).read_bytes(), b'release-smoke')
            self.assertTrue((bundle / 'categories.txt').is_file())
            self.assertTrue(launcher.is_file())
            # Building twice must produce identical ZIP hashes, not timestamp-dependent archives.
            subprocess.run([sys.executable, str(builder), '--output', str(output), '--version', '1.0.0'], check=True,
                           capture_output=True, timeout=30)
            for archive in archives:
                self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), checksums[archive.name])


if __name__ == '__main__':
    unittest.main(verbosity=2)
