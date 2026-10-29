# Windows PowerShell 5.1+ (Windows 10/11); no modules required.
$ErrorActionPreference = 'Stop'
$apply = $false
$root = $PSScriptRoot
try {
    for ($i = 0; $i -lt $args.Count; $i++) {
        switch -Exact ($args[$i]) {
            '--apply' { $apply = $true }
            '--dry-run' { $apply = $false }
            '--help' { Write-Output 'Usage: sort-downloads.bat [--path FOLDER] [--dry-run | --apply]'; exit 0 }
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
    foreach ($line in [IO.File]::ReadAllLines((Join-Path $PSScriptRoot 'categories.txt'))) {
        if (-not $line.Trim()) { continue }
        $parts = $line.Trim() -split '\s+'
        if ($parts.Count -lt 2 -or $parts[0] -cnotmatch '^[a-z]+$') { throw 'Invalid categories.txt' }
        foreach ($ext in $parts[1..($parts.Count - 1)]) {
            if ($ext -cnotmatch '^[a-z0-9]+$' -or $map.ContainsKey($ext)) { throw 'Invalid or duplicate extension' }
            $map[$ext] = $parts[0]
        }
    }
    # Expand 8.3 aliases once so identities match Get-ChildItem's long paths.
    $scriptPath = (Get-Item -LiteralPath $PSCommandPath -Force).FullName
    $launcherPath = $null
    if ($env:DOWNLOADS_SORTER_LAUNCHER) {
        $launcherPath = (Get-Item -LiteralPath $env:DOWNLOADS_SORTER_LAUNCHER -Force).FullName
    }
    $errors = 0
    $moved = 0
    $planned = 0
    foreach ($file in @(Get-ChildItem -LiteralPath $root -File -Force)) {
        if (@('sort-downloads.bat', 'sort-downloads.ps1', 'sort-downloads-legacy.bat', 'sort-downloads-legacy.js', 'sort-downloads.sh', 'sort downloads.command', 'categories.txt', 'readme.md', 'license') -contains $file.Name.ToLowerInvariant()) { continue }
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
