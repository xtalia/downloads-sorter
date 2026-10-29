"""End-to-end tests against native interpreters; never touch real Downloads."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
VARIANT = os.environ.get('SORTER_VARIANT', 'modern' if os.name == 'nt' else 'linux')
SCRIPTS = {
    'modern': 'windows/sort-downloads.ps1',
    'legacy': 'windows/sort-downloads-legacy.js',
    'linux': 'linux/sort-downloads.sh',
    'macos': 'macos/Sort Downloads.command',
}


class SorterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sorter-tests-', dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'Downloads space & (test)! %name%'
        self.root.mkdir()

    def run_sorter(self, *args, root=None, script=None, cwd=None, default_root=False):
        script = script or REPO / SCRIPTS[VARIANT]
        self.assertTrue(script.is_file(), f'Missing native sorter: {script}')
        if VARIANT == 'modern':
            command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)]
        elif VARIANT == 'legacy':
            command = ['cscript.exe', '//nologo', str(script)]
        else:
            interpreter = os.environ.get('SORTER_BASH') or ('/bin/bash' if sys.platform == 'darwin' else shutil.which('bash'))
            command = [interpreter, script.as_posix()]
        if not default_root:
            command += ['--path', Path(root or self.root).as_posix()]
        command += args
        return subprocess.run(command, capture_output=True, timeout=90, cwd=cwd)

    def copy_bundle(self, name='bundle'):
        source = REPO / SCRIPTS[VARIANT]
        bundle = Path(self.temp.name) / name
        shutil.copytree(source.parent, bundle)
        return bundle / source.name

    @unittest.skipIf(os.name == 'nt', 'POSIX interpreters only')
    def test_posix_initially_empty_extension_arrays_are_safe(self):
        script = self.copy_bundle()
        (self.root / 'photo.JPG').write_bytes(b'photo')
        result = self.run_sorter('--apply', script=script)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'photos' / 'photo.JPG').read_bytes(), b'photo')

    @unittest.skipIf(os.name == 'nt', 'POSIX-only directory characters')
    def test_posix_selected_root_trailing_newline_is_literal(self):
        sibling = Path(self.temp.name) / 'target'
        selected = Path(self.temp.name) / 'target\n'
        sibling.mkdir()
        selected.mkdir()
        (sibling / 'unselected.JPG').write_bytes(b'unselected')
        (selected / 'intended.JPG').write_bytes(b'intended')
        result = self.run_sorter('--apply', root=selected)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((sibling / 'unselected.JPG').is_file(), result.stdout + result.stderr)
        self.assertEqual((sibling / 'unselected.JPG').read_bytes(), b'unselected')
        self.assertEqual((selected / 'photos' / 'intended.JPG').read_bytes(), b'intended')

    @unittest.skipIf(os.name == 'nt', 'POSIX-only directory characters')
    def test_posix_bundle_directory_trailing_newline_is_literal(self):
        script = self.copy_bundle('bundle\n')
        sibling_script = self.copy_bundle('bundle')
        (sibling_script.parent / 'unselected.JPG').write_bytes(b'unselected')
        (script.parent / 'intended.JPG').write_bytes(b'intended')
        result = self.run_sorter('--apply', script=script, default_root=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((sibling_script.parent / 'unselected.JPG').is_file(), result.stdout + result.stderr)
        self.assertEqual((sibling_script.parent / 'unselected.JPG').read_bytes(), b'unselected')
        self.assertEqual((script.parent / 'photos' / 'intended.JPG').read_bytes(), b'intended')

    @unittest.skipUnless(os.name == 'nt' and VARIANT in {'modern', 'legacy'},
                         'Native Windows BAT launchers only')
    def test_renamed_windows_launcher_never_moves(self):
        script = self.copy_bundle('launcher space & (test)! %name%')
        original = script.with_name('sort-downloads.bat' if VARIANT == 'modern'
                                    else 'sort-downloads-legacy.bat')
        launcher = original.with_name('renamed & (launcher)!.bat')
        original.rename(launcher)
        before = launcher.read_bytes()
        (script.parent / 'photo.JPG').write_bytes(b'photo')
        result = subprocess.run(
            f'cmd.exe /d /v:off /s /c ""{launcher.name}" --apply"',
            cwd=script.parent, capture_output=True, timeout=30)
        self.assertTrue(launcher.is_file(), result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(launcher.read_bytes(), before)
        self.assertEqual((script.parent / 'photos' / 'photo.JPG').read_bytes(), b'photo')
        self.assertFalse((script.parent / 'programs' / launcher.name).exists())

    @unittest.skipUnless(os.name == 'nt' and VARIANT in {'modern', 'legacy'},
                         'Native Windows BAT launchers only')
    def test_renamed_windows_launcher_short_path_cwd_never_moves(self):
        import ctypes
        from ctypes import wintypes

        script = self.copy_bundle('launcher short alias space & (test)!')
        original = script.with_name('sort-downloads.bat' if VARIANT == 'modern'
                                    else 'sort-downloads-legacy.bat')
        launcher = original.with_name('renamed & (launcher)!.bat')
        original.rename(launcher)
        before = launcher.read_bytes()
        long_cwd = str(script.parent.resolve())
        get_short_path = ctypes.WinDLL('kernel32', use_last_error=True).GetShortPathNameW
        get_short_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        get_short_path.restype = wintypes.DWORD
        size = get_short_path(long_cwd, None, 0)
        if not size:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_unicode_buffer(size)
        length = get_short_path(long_cwd, buffer, size)
        if not length:
            raise ctypes.WinError(ctypes.get_last_error())
        self.assertLess(length, size)
        short_cwd = buffer.value
        if os.path.normcase(short_cwd) == os.path.normcase(long_cwd):
            self.skipTest('Filesystem provides no distinct 8.3 short-path alias')
        (script.parent / 'photo.JPG').write_bytes(b'photo')
        (script.parent / 'ordinary.bat').write_bytes(b'ordinary program')
        result = subprocess.run(
            f'cmd.exe /d /v:off /s /c ""{launcher.name}" --apply"',
            cwd=short_cwd, capture_output=True, timeout=30)
        self.assertTrue(launcher.is_file(), result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(launcher.read_bytes(), before)
        self.assertEqual((script.parent / 'photos' / 'photo.JPG').read_bytes(), b'photo')
        self.assertFalse((script.parent / 'programs' / launcher.name).exists())
        self.assertEqual((script.parent / 'programs' / 'ordinary.bat').read_bytes(),
                         b'ordinary program')
        self.assertFalse((script.parent / 'ordinary.bat').exists())






    @unittest.skipIf(os.name == 'nt', 'POSIX-only filename characters')
    def test_posix_trailing_newline_extension_stays_unknown(self):
        names = ['unknown.JPG\n', 'unknown.JPG\n\n']
        for name in names:
            (self.root / name).write_bytes(b'stay')
        (self.root / 'known.JPG').write_bytes(b'photo')
        result = self.run_sorter('--apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in names:
            self.assertTrue((self.root / name).is_file(), result.stdout + result.stderr)
            self.assertEqual((self.root / name).read_bytes(), b'stay')
        self.assertEqual((self.root / 'photos' / 'known.JPG').read_bytes(), b'photo')

    def test_category_link_cannot_escape_target(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        link = self.root / 'photos'
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(outside), str(link))
        else:
            link.symlink_to(outside, target_is_directory=True)
        (self.root / 'escape.JPG').write_bytes(b'stay')
        result = self.run_sorter('--apply')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'escape.JPG').read_bytes(), b'stay')
        self.assertEqual(list(outside.iterdir()), [])

    def test_source_symlinks_are_left_alone(self):
        outside = Path(self.temp.name) / 'outside.JPG'
        outside.write_bytes(b'outside')
        link = self.root / 'linked.JPG'
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f'Cannot create symlink on this host: {exc}')
        result = self.run_sorter('--apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertEqual(outside.read_bytes(), b'outside')
        self.assertFalse((self.root / 'photos').exists())

    def test_tool_files_never_move(self):
        names = ['sort-downloads.bat', 'sort-downloads.ps1',
                 'sort-downloads-legacy.bat', 'sort-downloads-legacy.js',
                 'sort-downloads.sh', 'Sort Downloads.command',
                 'categories.txt', 'README.md', 'LICENSE', 'sort-downloads.py']
        for name in names:
            (self.root / name).write_bytes(b'tool')
        result = self.run_sorter('--apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in names:
            self.assertEqual((self.root / name).read_bytes(), b'tool')

    def test_default_moves_immediately(self):
        (self.root / 'photo.HEIC').write_bytes(b'photo')
        result = self.run_sorter()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(b'MOVED:', result.stdout)
        self.assertFalse((self.root / 'photo.HEIC').exists())
        self.assertEqual((self.root / 'photos' / 'photo.HEIC').read_bytes(), b'photo')

    def test_no_arguments_moves_files_in_script_directory(self):
        script = self.copy_bundle()
        (script.parent / 'photo.JPG').write_bytes(b'photo')
        result = self.run_sorter(script=script, default_root=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((script.parent / 'photos' / 'photo.JPG').read_bytes(), b'photo')
        self.assertFalse((script.parent / 'photo.JPG').exists())

    def test_explicit_dry_run_does_not_change_anything(self):
        (self.root / 'preview.HEIC').write_bytes(b'preview')
        before = sorted(p.name for p in self.root.iterdir())
        result = self.run_sorter('--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(b'PLAN:', result.stdout)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), before)
        self.assertEqual((self.root / 'preview.HEIC').read_bytes(), b'preview')

    def test_explicit_dry_run_overrides_apply(self):
        (self.root / 'preview.JPG').write_bytes(b'preview')
        result = self.run_sorter('--apply', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / 'preview.JPG').is_file())
        self.assertFalse((self.root / 'photos').exists())

    def test_existing_destination_is_never_overwritten(self):
        (self.root / 'photos').mkdir()
        (self.root / 'photos' / 'same.JPG').write_bytes(b'old')
        (self.root / 'same.JPG').write_bytes(b'new')
        result = self.run_sorter('--apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'photos' / 'same.JPG').read_bytes(), b'old')
        self.assertEqual((self.root / 'same.JPG').read_bytes(), b'new')
        self.assertIn(b'SKIP', result.stdout)

    def test_directories_unknown_downloads_and_torrents_stay(self):
        names = ['unknown.thing', 'README', 'download.JPG.part', 'download.crdownload',
                 'keep.TORRENT', 'keep.MAGNET']
        for name in names:
            (self.root / name).write_bytes(b'keep')
        nested = self.root / 'folder.JPG'
        nested.mkdir()
        (nested / 'inside.JPG').write_bytes(b'keep')
        result = self.run_sorter('--apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in names:
            self.assertEqual((self.root / name).read_bytes(), b'keep')
        self.assertEqual((nested / 'inside.JPG').read_bytes(), b'keep')
        self.assertFalse((self.root / 'photos').exists())

    def test_all_categories_and_unambiguous_dmg_tiff(self):
        cases = {'bundle.TAR.GZ': 'archives', 'disk.DMG': 'iso', 'song.OPUS': 'music',
                 'clip.Mp4': 'video', 'setup.MSI': 'programs', 'scan.TIFF': 'photos',
                 'picture.AVIF': 'images', 'book.PDF': 'docs'}
        for name in cases:
            (self.root / name).write_bytes(name.encode())
        result = self.run_sorter('--apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name, category in cases.items():
            self.assertEqual((self.root / category / name).read_bytes(), name.encode())

    def test_unicode_spaces_and_shell_characters(self):
        name = 'Фото пробел & (скобки)! %file% [1] — тест.JPG'
        (self.root / name).write_bytes(bytes(range(256)))
        result = self.run_sorter('--apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'photos' / name).read_bytes(), bytes(range(256)))

    def test_hidden_file_is_sorted(self):
        (self.root / '.hidden.JPG').write_bytes(b'hidden')
        result = self.run_sorter('--apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'photos' / '.hidden.JPG').read_bytes(), b'hidden')

    def test_repeated_run_is_idempotent(self):
        (self.root / 'once.JPG').write_bytes(b'once')
        for _ in range(2):
            result = self.run_sorter('--apply')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'photos' / 'once.JPG').read_bytes(), b'once')
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['photos'])

    def test_invalid_arguments_fail_without_changes(self):
        (self.root / 'stay.JPG').write_bytes(b'stay')
        for args in [('--unknown',), ('--path',)]:
            result = self.run_sorter(*args)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['stay.JPG'])

    def test_missing_directory_is_not_created(self):
        missing = self.root / 'missing'
        result = self.run_sorter('--apply', root=missing)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse(missing.exists())

    def test_blocked_category_reports_error_and_keeps_source(self):
        (self.root / 'photos').write_bytes(b'not a directory')
        (self.root / 'stay.JPG').write_bytes(b'stay')
        result = self.run_sorter('--apply')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual((self.root / 'stay.JPG').read_bytes(), b'stay')
        self.assertEqual((self.root / 'photos').read_bytes(), b'not a directory')

    @unittest.skipIf(os.name == 'nt', 'POSIX-only filename characters')
    def test_posix_newline_and_leading_dash_names(self):
        for name in ['-option.JPG', 'line\nbreak.JPG', "quote'file.JPG"]:
            (self.root / name).write_bytes(b'data')
        result = self.run_sorter('--apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ['-option.JPG', 'line\nbreak.JPG', "quote'file.JPG"]:
            self.assertEqual((self.root / 'photos' / name).read_bytes(), b'data')

    def test_all_supported_extensions_match_python(self):
        import runpy
        categories = runpy.run_path(str(REPO / 'python' / 'sort-downloads.py'))['CATEGORIES']
        self.assertEqual(len(categories), 145)
        for ext in categories:
            (self.root / ('supported.' + ext.upper())).write_bytes(ext.encode())
        result = self.run_sorter()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for ext, category in categories.items():
            self.assertEqual((self.root / category / ('supported.' + ext.upper())).read_bytes(), ext.encode())

    def test_case_insensitive_extensions(self):
        names = ['lower.jpg', 'upper.JPG', 'mixed.JpG', 'phone.HEIC']
        for name in names:
            (self.root / name).write_bytes(name.encode())
        result = self.run_sorter('--apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in names:
            self.assertEqual((self.root / 'photos' / name).read_bytes(), name.encode())
            self.assertFalse((self.root / name).exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
