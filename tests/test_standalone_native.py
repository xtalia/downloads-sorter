"""Exercise each final native entry point with no runtime sidecar files."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
ENTRIES = {
    'modern': 'windows/sort-downloads.bat',
    'legacy': 'windows/sort-downloads-legacy.bat',
    'linux': 'linux/sort-downloads.sh',
    'macos': 'macos/Sort Downloads.command',
}
SELECTED = os.environ.get('STANDALONE_VARIANT') or os.environ.get('SORTER_VARIANT')
VARIANTS = [SELECTED] if SELECTED else (list(ENTRIES) if os.name == 'nt' else ['linux', 'macos'])


class StandaloneNativeTest(unittest.TestCase):
    def setUp(self):
        scratch = os.environ.get('SORTER_TEST_SCRATCH') or os.environ.get('TMPDIR')
        self.temp = tempfile.TemporaryDirectory(prefix='standalone-native-', dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)

    def copy_entry(self, variant, name=None):
        original = REPO / ENTRIES[variant]
        folder = self.base / variant / 'single entry space & (test)! %name%'
        folder.mkdir(parents=True)
        entry = folder / (name or original.name)
        shutil.copyfile(original, entry)
        self.assertEqual(list(folder.iterdir()), [entry])
        return entry

    def launch(self, variant, entry, *args, cwd=None):
        env = os.environ.copy()
        if variant in ('modern', 'legacy'):
            env['SORTER_TEST_ENTRY'] = str(entry)
            words = []
            for i, arg in enumerate(args):
                env['SORTER_TEST_ARG_' + str(i)] = str(arg)
                words.append('"%SORTER_TEST_ARG_' + str(i) + '%"')
            command = 'cmd.exe /d /v:off /s /c ""%SORTER_TEST_ENTRY%" ' + ' '.join(words) + '"'
        else:
            bash = os.environ.get('SORTER_BASH') or ('/bin/bash' if sys.platform == 'darwin' else shutil.which('bash'))
            command = [bash, entry.as_posix(), *[str(a) for a in args]]
        # A real BAT no-argument launch pauses only AFTER sorting.
        return subprocess.run(command, input=b'\n', capture_output=True, timeout=40,
                              cwd=cwd or self.base, env=env)

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_single_file_no_arguments_moves_photo(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                entry = self.copy_entry(variant)
                (entry.parent / 'photo.JPG').write_bytes(b'photo')
                result = self.launch(variant, entry)
                self.assert_success(result)
                self.assertEqual((entry.parent / 'photos' / 'photo.JPG').read_bytes(), b'photo')
                self.assertTrue(entry.is_file())
                self.assertFalse((entry.parent / 'photo.JPG').exists())

    def test_dry_run_preserves_exact_tree(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                entry = self.copy_entry(variant)
                photo = entry.parent / 'preview.JPG'
                photo.write_bytes(b'preview')
                before = {p.name: p.read_bytes() for p in entry.parent.iterdir()}
                result = self.launch(variant, entry, '--dry-run')
                self.assert_success(result)
                self.assertIn(b'PLAN:', result.stdout)
                self.assertEqual({p.name: p.read_bytes() for p in entry.parent.iterdir()}, before)

    def test_literal_selected_path_from_other_cwd(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                entry = self.copy_entry(variant)
                selected = self.base / variant / "Фото & (target)! %name% [1] ' $value; folder"
                selected.mkdir()
                (selected / 'Фото & (file)! %file%.JPG').write_bytes(b'selected')
                (entry.parent / 'unselected.JPG').write_bytes(b'unchanged')
                result = self.launch(variant, entry, '--path', selected.as_posix())
                self.assert_success(result)
                self.assertEqual((selected / 'photos' / 'Фото & (file)! %file%.JPG').read_bytes(), b'selected')
                self.assertEqual((entry.parent / 'unselected.JPG').read_bytes(), b'unchanged')

    def test_existing_destination_is_never_overwritten(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                entry = self.copy_entry(variant)
                (entry.parent / 'photos').mkdir()
                (entry.parent / 'photos' / 'same.JPG').write_bytes(b'old')
                (entry.parent / 'same.JPG').write_bytes(b'new')
                result = self.launch(variant, entry, '--apply')
                self.assert_success(result)
                self.assertEqual((entry.parent / 'same.JPG').read_bytes(), b'new')
                self.assertEqual((entry.parent / 'photos' / 'same.JPG').read_bytes(), b'old')

    def test_all_embedded_extensions_match_authoritative_table(self):
        table = """archives zip gz tgz rar 7z tar bz2 xz cab arj lzh ace 001 zst bz z lz lzma txz tbz2
iso iso img bin cue nrg mdf mds vcd dmg vhd vhdx vdi qcow2
music mp3 wav flac aac ogg wma m4a aiff aif alac ape pls m3u m3u8 aimppl opus mid midi
video avi mov mp4 mkv 3gp webm flv wmv mpeg mpg vob m4v ts mts m2ts divx f4v
programs exe msi msix appx apk pkg bat sh deb rpm jar py com cmd scr ps1 command appimage
photos jpg jpeg jpe heic heif cr2 cr3 nef arw dng raw orf rw2 srw tif tiff pef bay raf
images png bmp gif svg webp ico psd ai xcf emf wmf dds jpf jpx avif jxl eps
docs pdf txt doc docx xls xlsx ods rtf odt ppt pptx csv djvu epub fb2 md tex log mobi azw azw3 odp ics"""
        expected = {ext: line.split()[0] for line in table.splitlines() for ext in line.split()[1:]}
        self.assertEqual(len(expected), 145)
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                entry = self.copy_entry(variant)
                for ext in expected:
                    (entry.parent / ('example.' + ext.upper())).write_bytes(ext.encode('ascii'))
                result = self.launch(variant, entry, '--apply')
                self.assert_success(result)
                for ext, category in expected.items():
                    self.assertEqual((entry.parent / category / ('example.' + ext.upper())).read_bytes(), ext.encode('ascii'))

    def test_last_mode_flag_wins(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                entry = self.copy_entry(variant)
                (entry.parent / 'photo.JPG').write_bytes(b'photo')
                result = self.launch(variant, entry, '--apply', '--dry-run')
                self.assert_success(result)
                self.assertTrue((entry.parent / 'photo.JPG').exists())
                self.assertFalse((entry.parent / 'photos').exists())
                result = self.launch(variant, entry, '--dry-run', '--apply')
                self.assert_success(result)
                self.assertEqual((entry.parent / 'photos' / 'photo.JPG').read_bytes(), b'photo')

    def test_invalid_arguments_fail_before_moving(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                entry = self.copy_entry(variant)
                (entry.parent / 'photo.JPG').write_bytes(b'photo')
                for args in [('--unknown',), ('--path',)]:
                    result = self.launch(variant, entry, *args)
                    self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual((entry.parent / 'photo.JPG').read_bytes(), b'photo')
                self.assertFalse((entry.parent / 'photos').exists())

    def test_category_link_cannot_escape_target(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                entry = self.copy_entry(variant)
                outside = self.base / variant / 'outside'
                outside.mkdir()
                link = entry.parent / 'photos'
                if os.name == 'nt':
                    import _winapi
                    _winapi.CreateJunction(str(outside), str(link))
                else:
                    link.symlink_to(outside, target_is_directory=True)
                (entry.parent / 'photo.JPG').write_bytes(b'photo')
                result = self.launch(variant, entry, '--apply')
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((entry.parent / 'photo.JPG').read_bytes(), b'photo')
                self.assertEqual(list(outside.iterdir()), [])

    def test_blocked_category_file_preserves_source(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant):
                entry = self.copy_entry(variant)
                (entry.parent / 'photos').write_bytes(b'blocker')
                (entry.parent / 'photo.JPG').write_bytes(b'photo')
                result = self.launch(variant, entry, '--apply')
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual((entry.parent / 'photo.JPG').read_bytes(), b'photo')
                self.assertEqual((entry.parent / 'photos').read_bytes(), b'blocker')

    @unittest.skipUnless(os.name == 'nt', 'Native Windows 8.3 CWD protection')
    def test_renamed_bat_from_short_alias_cwd_protects_itself(self):
        import ctypes
        from ctypes import wintypes
        get_short = ctypes.WinDLL('kernel32', use_last_error=True).GetShortPathNameW
        get_short.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        get_short.restype = wintypes.DWORD
        applicable = [v for v in VARIANTS if v in ('modern', 'legacy')]
        if not applicable:
            self.skipTest('BAT variants only')
        for variant in applicable:
            with self.subTest(variant=variant):
                entry = self.copy_entry(variant, 'renamed & (launcher)!.bat')
                long_cwd = str(entry.parent.resolve())
                size = get_short(long_cwd, None, 0)
                self.assertGreater(size, 0)
                buffer = ctypes.create_unicode_buffer(size)
                self.assertGreater(get_short(long_cwd, buffer, size), 0)
                if os.path.normcase(buffer.value) == os.path.normcase(long_cwd):
                    self.skipTest('Filesystem provides no distinct 8.3 alias')
                before = entry.read_bytes()
                (entry.parent / 'photo.JPG').write_bytes(b'photo')
                (entry.parent / 'ordinary.bat').write_bytes(b'ordinary')
                for explicit_root in (False, True):
                    args = ('--path', long_cwd) if explicit_root else ()
                    result = self.launch(variant, Path(entry.name), *args, cwd=buffer.value)
                    self.assert_success(result)
                    self.assertTrue(entry.is_file(), result.stdout + result.stderr)
                    self.assertEqual(entry.read_bytes(), before)
                    self.assertFalse((entry.parent / 'programs' / entry.name).exists())
                    self.assertEqual((entry.parent / 'photos' / 'photo.JPG').read_bytes(), b'photo')
                    self.assertEqual((entry.parent / 'programs' / 'ordinary.bat').read_bytes(), b'ordinary')


if __name__ == '__main__':
    unittest.main(verbosity=2)
