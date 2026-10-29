#!/usr/bin/env python3
"""Sort this script's folder immediately. Python 3.8+, standard library only.

Usage: python sort-downloads.py [--path FOLDER] [--dry-run | --apply]
No categories.txt or installation is needed. Existing files are never replaced.
"""
import argparse
import errno
import os
from pathlib import Path
import re
import shutil
import stat
import sys

# Kept identical to the native variants' categories.txt; tested for parity.
CATEGORY_TABLE = """archives zip gz tgz rar 7z tar bz2 xz cab arj lzh ace 001 zst bz z lz lzma txz tbz2
iso iso img bin cue nrg mdf mds vcd dmg vhd vhdx vdi qcow2
music mp3 wav flac aac ogg wma m4a aiff aif alac ape pls m3u m3u8 aimppl opus mid midi
video avi mov mp4 mkv 3gp webm flv wmv mpeg mpg vob m4v ts mts m2ts divx f4v
programs exe msi msix appx apk pkg bat sh deb rpm jar py com cmd scr ps1 command appimage
photos jpg jpeg jpe heic heif cr2 cr3 nef arw dng raw orf rw2 srw tif tiff pef bay raf
images png bmp gif svg webp ico psd ai xcf emf wmf dds jpf jpx avif jxl eps
docs pdf txt doc docx xls xlsx ods rtf odt ppt pptx csv djvu epub fb2 md tex log mobi azw azw3 odp ics
"""
CATEGORIES = {ext: line.split()[0] for line in CATEGORY_TABLE.splitlines()
              for ext in line.split()[1:]}
RESERVED = {
    'sort-downloads.py', 'sort-downloads.bat', 'sort-downloads.ps1',
    'sort-downloads-legacy.bat', 'sort-downloads-legacy.js', 'sort-downloads.sh',
    'sort downloads.command', 'categories.txt', 'readme.md', 'license',
}


def is_reparse(info):
    """Also detect junctions on Windows without requiring Python 3.12."""
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, 'st_file_attributes', 0) & 0x400)


def move_no_overwrite(source, destination):
    """Exclusive hardlink+unlink; exclusive copy fallback for FAT/network disks.

    Hardlinks avoid copying large media on ordinary local filesystems. If they
    are unsupported, copying must finish before the source is removed. There is
    no overwrite operation in either path. Concurrent folder mutation is outside
    this tool's contract, as with the native variants.
    """
    created = False
    try:
        try:
            os.link(str(source), str(destination), follow_symlinks=False)
            created = True
        except FileExistsError:
            raise
        except OSError as exc:
            fallback = {errno.EXDEV, errno.EPERM, errno.EACCES, errno.EINVAL,
                        errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}
            if exc.errno not in fallback:
                raise
            with source.open('rb') as reader, destination.open('xb') as writer:
                created = True
                shutil.copyfileobj(reader, writer, length=1024 * 1024)
            shutil.copystat(str(source), str(destination), follow_symlinks=False)
        source.unlink()
    except OSError:
        if created:
            try:
                destination.unlink()
            except OSError:
                pass  # Keep both copies rather than risk the source's contents.
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, default=Path(__file__).resolve().parent,
                        help='Folder to sort (default: this script\'s folder)')
    parser.add_argument('--dry-run', dest='apply', action='store_false',
                        help='Preview without moving files or creating folders')
    parser.add_argument('--apply', dest='apply', action='store_true',
                        help='Move files (the default; retained for compatibility)')
    parser.set_defaults(apply=True)
    args = parser.parse_args(argv)
    try:
        root = args.path.resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError(str(root))
        entries = list(root.iterdir())
        script = Path(__file__).resolve()
    except OSError as exc:
        print('ERROR: {}'.format(exc), file=sys.stderr)
        return 2
    moved = planned = errors = 0
    for source in entries:
        try:
            info = source.lstat()
            if is_reparse(info) or not stat.S_ISREG(info.st_mode):
                continue
            if source.name.lower() in RESERVED or source.resolve() == script:
                continue
            # Match literal ASCII bytes before case conversion; do not strip.
            extension = source.name.rsplit('.', 1)[-1] if '.' in source.name else ''
            if not re.fullmatch(r'[A-Za-z0-9]+', extension):
                continue
            category = CATEGORIES.get(extension.lower())
            if not category:
                continue
            folder = root / category
            if os.path.lexists(str(folder)):
                folder_info = folder.lstat()
                if is_reparse(folder_info) or not stat.S_ISDIR(folder_info.st_mode):
                    raise OSError('Unsafe category directory: {}'.format(folder))
            destination = folder / source.name
            if os.path.lexists(str(destination)):
                print('SKIP exists: {}'.format(destination))
                continue
            planned += 1
            if not args.apply:
                print('PLAN: {} -> {}'.format(source, destination))
                continue
            folder.mkdir(exist_ok=True)
            try:
                move_no_overwrite(source, destination)
            except FileExistsError:
                print('SKIP exists: {}'.format(destination))
                continue
            moved += 1
            print('MOVED: {} -> {}'.format(source.name, category))
        except OSError as exc:
            errors += 1
            print('ERROR: {}: {}'.format(source, exc), file=sys.stderr)
    print('Done. Planned={} Moved={} Errors={} Apply={}'.format(
        planned, moved, errors, args.apply))
    return 1 if errors else 0


if __name__ == '__main__':
    # Names outside the console code page must not fail after a successful move.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(errors='backslashreplace')
    sys.exit(main())
