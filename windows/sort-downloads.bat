@echo off
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
# Windows PowerShell 5.1+ (Windows 10/11); no modules required.
$ErrorActionPreference = 'Stop'
$apply = $true
$sorterPath = if ($env:DOWNLOADS_SORTER_EMBEDDED -eq '1') { $env:DOWNLOADS_SORTER_LAUNCHER } else { $PSCommandPath }
$root = Split-Path -LiteralPath $sorterPath
try {
    for ($i = 0; $i -lt $args.Count; $i++) {
        switch -Exact ($args[$i]) {
            '--apply' { $apply = $true }
            '--dry-run' { $apply = $false }
            '--help' { Write-Output 'Usage: sort-downloads.bat [--path FOLDER] [--dry-run | --apply] (default: move files)'; exit 0 }
            '--path' {
                $i++
                if ($i -ge $args.Count) { throw '--path requires a folder' }
                $root = $args[$i]
            }
            default { throw "Unknown argument: $($args[$i])" }
        }
    }
    $item = Get-Item -LiteralPath $root -Force
    if (-not $item.PSIsContainer) { throw 'Target must be a directory' }
    $root = $item.FullName
    $map = @{}
    $categoryTable = @'
archives zip gz tgz rar 7z tar bz2 xz cab arj lzh ace 001 zst bz z lz lzma txz tbz2
iso iso img bin cue nrg mdf mds vcd dmg vhd vhdx vdi qcow2
music mp3 wav flac aac ogg wma m4a aiff aif alac ape pls m3u m3u8 aimppl opus mid midi
video avi mov mp4 mkv 3gp webm flv wmv mpeg mpg vob m4v ts mts m2ts divx f4v
programs exe msi msix appx apk pkg bat sh deb rpm jar py com cmd scr ps1 command appimage
photos jpg jpeg jpe heic heif cr2 cr3 nef arw dng raw orf rw2 srw tif tiff pef bay raf
images png bmp gif svg webp ico psd ai xcf emf wmf dds jpf jpx avif jxl eps
docs pdf txt doc docx xls xlsx ods rtf odt ppt pptx csv djvu epub fb2 md tex log mobi azw azw3 odp ics
'@
    foreach ($line in ($categoryTable -split '\r?\n')) {
        if (-not $line.Trim()) { continue }
        $parts = $line.Trim() -split '\s+'
        if ($parts.Count -lt 2 -or $parts[0] -cnotmatch '^[a-z]+$') { throw 'Invalid embedded category table' }
        foreach ($ext in $parts[1..($parts.Count - 1)]) {
            if ($ext -cnotmatch '^[a-z0-9]+$' -or $map.ContainsKey($ext)) { throw 'Invalid or duplicate extension' }
            $map[$ext] = $parts[0]
        }
    }
    # Expand 8.3 aliases once so identities match Get-ChildItem's long paths.
    $scriptPath = (Get-Item -LiteralPath $sorterPath -Force).FullName
    $launcherPath = $null
    if ($env:DOWNLOADS_SORTER_LAUNCHER) {
        $launcherPath = (Get-Item -LiteralPath $env:DOWNLOADS_SORTER_LAUNCHER -Force).FullName
    }
    $errors = 0
    $moved = 0
    $planned = 0
    foreach ($file in @(Get-ChildItem -LiteralPath $root -File -Force)) {
        if (@('sort-downloads.py', 'sort-downloads.bat', 'sort-downloads.ps1', 'sort-downloads-legacy.bat', 'sort-downloads-legacy.js', 'sort-downloads.sh', 'sort downloads.command', 'categories.txt', 'readme.md', 'license') -contains $file.Name.ToLowerInvariant()) { continue }
        if (($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            [string]::Equals($file.FullName, $scriptPath, [StringComparison]::OrdinalIgnoreCase) -or
            [string]::Equals($file.FullName, $launcherPath, [StringComparison]::OrdinalIgnoreCase)) { continue }
        if (-not $file.Extension) { continue }
        $ext = $file.Extension.Substring(1).ToLowerInvariant()
        if (-not $map.ContainsKey($ext)) { continue }
        $folder = Join-Path $root $map[$ext]
        if (Test-Path -LiteralPath $folder) {
            $target = Get-Item -LiteralPath $folder -Force
            if (-not $target.PSIsContainer -or ($target.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                $errors++; Write-Output "ERROR: Unsafe category directory: $folder"; continue
            }
        }
        $dest = Join-Path $folder $file.Name
        if (Test-Path -LiteralPath $dest) { Write-Output "SKIP exists: $dest"; continue }
        $planned++
        if (-not $apply) { Write-Output "PLAN: $($file.FullName) -> $dest"; continue }
        try {
            [void][IO.Directory]::CreateDirectory($folder)
            [IO.File]::Move($file.FullName, $dest)
            $moved++
            Write-Output "MOVED: $($file.Name) -> $($map[$ext])"
        } catch { $errors++; Write-Output "ERROR: $($_.Exception.Message)" }
    }
    Write-Output "Done. Planned=$planned Moved=$moved Errors=$errors Apply=$apply"
    if ($errors) { exit 1 }
    exit 0
} catch { Write-Output "ERROR: $($_.Exception.Message)"; exit 2 }
