"""Regenerate standalone Windows BATs from the developer-only embedded cores.

No files are extracted at runtime. Run after changing either canonical core.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODERN_HEADER = r'''@echo off
setlocal DisableDelayedExpansion
set "DOWNLOADS_SORTER_LAUNCHER=%~f0"
set "DOWNLOADS_SORTER_EMBEDDED=1"
set "DOWNLOADS_SORTER_PATH="
set "DOWNLOADS_SORTER_MODE=--apply"
set "DOWNLOADS_SORTER_PAUSE="
if "%~1"=="" set "DOWNLOADS_SORTER_PAUSE=1"
:sorter_args
if "%~1"=="" goto sorter_run
if "%~1"=="--path" goto sorter_path
if "%~1"=="--apply" goto sorter_apply
if "%~1"=="--dry-run" goto sorter_preview
if "%~1"=="--help" goto sorter_help
echo ERROR: Unknown argument
exit /b 2
:sorter_path
if "%~2"=="" goto sorter_missing_path
set "DOWNLOADS_SORTER_PATH=%~2"
shift
shift
goto sorter_args
:sorter_missing_path
echo ERROR: --path requires a folder
exit /b 2
:sorter_apply
set "DOWNLOADS_SORTER_MODE=--apply"
shift
goto sorter_args
:sorter_preview
set "DOWNLOADS_SORTER_MODE=--dry-run"
shift
goto sorter_args
:sorter_help
set "DOWNLOADS_SORTER_MODE=--help"
goto sorter_run
:sorter_run
rem Only fixed code enters -Command. Literal user data travels in scoped environment variables.
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$text=[IO.File]::ReadAllText($env:DOWNLOADS_SORTER_LAUNCHER); $body=($text -split '(?m)^# DOWNLOADS_SORTER_POWERSHELL_BODY\r?$',2)[1]; $a=@(); if ($env:DOWNLOADS_SORTER_PATH) { $a+=@('--path',$env:DOWNLOADS_SORTER_PATH) }; $a+=$env:DOWNLOADS_SORTER_MODE; & ([scriptblock]::Create($body)) @a"
set "result=%errorlevel%"
if defined DOWNLOADS_SORTER_PAUSE pause
exit /b %result%
# DOWNLOADS_SORTER_POWERSHELL_BODY
'''
LEGACY_HEADER = r'''@if (@X)==(@Y) @end /*
@echo off
setlocal DisableDelayedExpansion
set "DOWNLOADS_SORTER_LAUNCHER=%~f0"
cscript.exe //E:JScript //nologo "%~f0" %*
set "result=%errorlevel%"
if "%~1"=="" pause
exit /b %result%
*/
'''


def main():
    for name, header, core in [
        ('sort-downloads.bat', MODERN_HEADER, 'sort-downloads.ps1'),
        ('sort-downloads-legacy.bat', LEGACY_HEADER, 'sort-downloads-legacy.js'),
    ]:
        body = (REPO / 'windows' / core).read_text(encoding='utf-8')
        content = (header + body).replace('\r\n', '\n').replace('\n', '\r\n')
        (REPO / 'windows' / name).write_bytes(content.encode('utf-8'))
        print('Generated windows/' + name)


if __name__ == '__main__':
    main()
