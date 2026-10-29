"""Build three deterministic, dependency-free platform ZIPs and SHA-256 sums."""
import argparse
import hashlib
from pathlib import Path
import re
import zipfile

REPO = Path(__file__).resolve().parents[1]
PLATFORM_FILES = {
    'windows': ('categories.txt', 'sort-downloads.bat', 'sort-downloads.ps1',
                'sort-downloads-legacy.bat', 'sort-downloads-legacy.js'),
    'linux': ('categories.txt', 'sort-downloads.sh'),
    'macos': ('categories.txt', 'Sort Downloads.command'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='1.0.0')
    parser.add_argument('--output', type=Path, default=REPO / 'dist')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', args.version):
        parser.error('version must use MAJOR.MINOR.PATCH')
    mappings = [(REPO / p / 'categories.txt').read_bytes().replace(b'\r\n', b'\n')
                for p in ('windows', 'linux', 'macos')]
    if mappings[0] != mappings[1] or mappings[0] != mappings[2]:
        parser.error('categories.txt differs across platforms')
    if (REPO / 'linux' / 'sort-downloads.sh').read_bytes() != (REPO / 'macos' / 'Sort Downloads.command').read_bytes():
        parser.error('Linux and macOS implementations must stay identical')
    args.output.mkdir(parents=True, exist_ok=True)
    checksums = []
    for platform in ('windows', 'linux', 'macos'):
        archive = args.output / f'downloads-sorter-{platform}-v{args.version}.zip'
        sources = sorted(REPO / platform / name for name in PLATFORM_FILES[platform])
        sources += [REPO / 'README.md', REPO / 'LICENSE']
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for source in sources:
                data = source.read_bytes().replace(b'\r\n', b'\n')
                if platform == 'windows' and source.suffix in {'.bat', '.ps1', '.js'}:
                    data = data.replace(b'\n', b'\r\n')
                info = zipfile.ZipInfo(source.name, date_time=(2020, 1, 1, 0, 0, 0))
                info.create_system = 3
                mode = 0o755 if source.suffix in {'.sh', '.command'} else 0o644
                info.external_attr = (0o100000 | mode) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, data)
        checksums.append(f'{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}')
        print(archive)
    (args.output / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='ascii', newline='\n')


if __name__ == '__main__':
    main()
