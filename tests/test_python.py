"""The universal script needs only Python's standard library and no sidecar files."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / 'python' / 'sort-downloads.py'


class PythonSorterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sorter-python-', dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'folder & (test)!'
        self.root.mkdir()

    def run_sorter(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--path', str(self.root), *args],
                              capture_output=True, timeout=30)

    def load_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('sorter_under_test', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_embedded_categories_match_native_table(self):
        module = self.load_module()
        expected = {}
        expected_table = """archives zip gz tgz rar 7z tar bz2 xz cab arj lzh ace 001 zst bz z lz lzma txz tbz2
iso iso img bin cue nrg mdf mds vcd dmg vhd vhdx vdi qcow2
music mp3 wav flac aac ogg wma m4a aiff aif alac ape pls m3u m3u8 aimppl opus mid midi
video avi mov mp4 mkv 3gp webm flv wmv mpeg mpg vob m4v ts mts m2ts divx f4v
programs exe msi msix appx apk pkg bat sh deb rpm jar py com cmd scr ps1 command appimage
photos jpg jpeg jpe heic heif cr2 cr3 nef arw dng raw orf rw2 srw tif tiff pef bay raf
images png bmp gif svg webp ico psd ai xcf emf wmf dds jpf jpx avif jxl eps
docs pdf txt doc docx xls xlsx ods rtf odt ppt pptx csv djvu epub fb2 md tex log mobi azw azw3 odp ics"""
        for line in expected_table.splitlines():
            category, *extensions = line.split()
            expected.update((ext, category) for ext in extensions)
        self.assertEqual(module.CATEGORIES, expected)
        for ext, category in expected.items():
            (self.root / ('file.' + ext.upper())).write_bytes(ext.encode())
        result = self.run_sorter()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for ext, category in expected.items():
            self.assertEqual((self.root / category / ('file.' + ext.upper())).read_bytes(), ext.encode())

    def test_dry_run_never_creates_directories_or_moves(self):
        (self.root / 'stay.JPG').write_bytes(b'stay')
        result = self.run_sorter('--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(b'PLAN:', result.stdout)
        self.assertEqual(list(self.root.iterdir()), [self.root / 'stay.JPG'])

    def test_last_mode_flag_wins(self):
        (self.root / 'photo.JPG').write_bytes(b'photo')
        result = self.run_sorter('--apply', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / 'photo.JPG').is_file())
        result = self.run_sorter('--dry-run', '--apply')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'photos' / 'photo.JPG').read_bytes(), b'photo')

    def test_existing_destination_and_subdirectories_remain(self):
        (self.root / 'photos').mkdir()
        (self.root / 'photos' / 'same.JPG').write_bytes(b'old')
        (self.root / 'same.JPG').write_bytes(b'new')
        (self.root / 'nested').mkdir()
        (self.root / 'nested' / 'inside.JPG').write_bytes(b'nested')
        for name in ('keep.TORRENT', 'keep.MAGNET', 'unknown.thing', 'partial.JPG.part', 'noext'):
            (self.root / name).write_bytes(b'keep')
        result = self.run_sorter()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'photos' / 'same.JPG').read_bytes(), b'old')
        self.assertEqual((self.root / 'same.JPG').read_bytes(), b'new')
        self.assertEqual((self.root / 'nested' / 'inside.JPG').read_bytes(), b'nested')
        for name in ('keep.TORRENT', 'keep.MAGNET', 'unknown.thing', 'partial.JPG.part', 'noext'):
            self.assertEqual((self.root / name).read_bytes(), b'keep')

    def test_blocked_category_preserves_source(self):
        (self.root / 'photos').write_bytes(b'blocked')
        (self.root / 'stay.JPG').write_bytes(b'stay')
        result = self.run_sorter()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual((self.root / 'stay.JPG').read_bytes(), b'stay')

    def test_category_link_cannot_escape(self):
        outside = Path(self.temp.name) / 'outside'
        outside.mkdir()
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(str(outside), str(self.root / 'photos'))
        else:
            (self.root / 'photos').symlink_to(outside, target_is_directory=True)
        (self.root / 'stay.JPG').write_bytes(b'stay')
        result = self.run_sorter()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual((self.root / 'stay.JPG').read_bytes(), b'stay')
        self.assertEqual(list(outside.iterdir()), [])

    def test_invalid_args_and_missing_root_fail(self):
        for args in [('--unknown',), ('--path',), ('--path', str(self.root / 'missing'))]:
            result = self.run_sorter(*args)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_unicode_mixed_case_and_idempotence(self):
        name = 'Фото & (тест)! %name% [1].JpG'
        (self.root / name).write_bytes(bytes(range(256)))
        for _ in range(2):
            result = self.run_sorter()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / 'photos' / name).read_bytes(), bytes(range(256)))

    def test_exclusive_copy_fallback_when_hardlinks_unsupported(self):
        import errno
        from unittest.mock import patch
        module = self.load_module()
        source, destination = self.root / 'source.JPG', self.root / 'dest.JPG'
        source.write_bytes(b'copy fallback')
        with patch.object(module.os, 'link', side_effect=OSError(errno.ENOTSUP, 'no hardlinks')):
            module.move_no_overwrite(source, destination)
        self.assertFalse(source.exists())
        self.assertEqual(destination.read_bytes(), b'copy fallback')

    def test_copy_fallback_never_overwrites_existing_target(self):
        import errno
        from unittest.mock import patch
        module = self.load_module()
        source, destination = self.root / 'source.JPG', self.root / 'dest.JPG'
        source.write_bytes(b'new')
        destination.write_bytes(b'old')
        with patch.object(module.os, 'link', side_effect=OSError(errno.ENOTSUP, 'no hardlinks')):
            with self.assertRaises(FileExistsError):
                module.move_no_overwrite(source, destination)
        self.assertEqual(source.read_bytes(), b'new')
        self.assertEqual(destination.read_bytes(), b'old')

    def test_failed_copy_rolls_back_partial_destination(self):
        import errno
        from unittest.mock import patch
        module = self.load_module()
        source, destination = self.root / 'source.JPG', self.root / 'dest.JPG'
        source.write_bytes(b'keep')
        with patch.object(module.os, 'link', side_effect=OSError(errno.ENOTSUP, 'no hardlinks')):
            with patch.object(module.shutil, 'copyfileobj', side_effect=OSError(errno.ENOSPC, 'disk full')):
                with self.assertRaises(OSError):
                    module.move_no_overwrite(source, destination)
        self.assertEqual(source.read_bytes(), b'keep')
        self.assertFalse(destination.exists())

    @unittest.skipIf(os.name == 'nt', 'POSIX-only path characters')
    def test_posix_trailing_newlines_are_literal(self):
        root = self.root / 'literal\n'
        root.mkdir()
        (root / 'keep.JPG\n').write_bytes(b'unknown')
        (root / 'known.JPG').write_bytes(b'photo')
        result = self.run_sorter('--path', str(root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((root / 'keep.JPG\n').read_bytes(), b'unknown')
        self.assertEqual((root / 'photos' / 'known.JPG').read_bytes(), b'photo')

    def test_source_symlink_is_not_moved(self):
        outside = Path(self.temp.name) / 'outside.JPG'
        outside.write_bytes(b'outside')
        link = self.root / 'link.JPG'
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest('Symlink privilege unavailable: {}'.format(exc))
        result = self.run_sorter()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(link.is_symlink())
        self.assertFalse((self.root / 'photos').exists())
        self.assertEqual(outside.read_bytes(), b'outside')

    def test_renamed_python_script_protects_itself(self):
        script = self.root / 'renamed script.py'
        script.write_bytes(SCRIPT.read_bytes())
        (self.root / 'ordinary.py').write_bytes(b'ordinary')
        result = subprocess.run([sys.executable, str(script)], capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(script.is_file())
        self.assertEqual((self.root / 'programs' / 'ordinary.py').read_bytes(), b'ordinary')

    def test_runtime_imports_only_standard_library(self):
        import ast
        tree = ast.parse(SCRIPT.read_text(), feature_version=(3, 8))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for item in node.names:
                    self.assertIn(item.name.split('.')[0], sys.stdlib_module_names)
            elif isinstance(node, ast.ImportFrom):
                self.assertIn(node.module.split('.')[0], sys.stdlib_module_names)

    def test_standalone_no_argument_run_moves_immediately(self):
        self.assertTrue(SCRIPT.is_file(), 'Missing standalone Python sorter')
        with tempfile.TemporaryDirectory(prefix='sorter-python-', dir=os.environ.get('TMPDIR')) as temp:
            root = Path(temp)
            script = root / 'sort-downloads.py'
            script.write_bytes(SCRIPT.read_bytes())
            (root / 'Фото.HEIC').write_bytes(b'photo')
            result = subprocess.run([sys.executable, str(script)], cwd=REPO,
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / 'photos' / 'Фото.HEIC').read_bytes(), b'photo')
            self.assertFalse((root / 'Фото.HEIC').exists())
            self.assertTrue(script.is_file())
            self.assertFalse((root / 'categories.txt').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
