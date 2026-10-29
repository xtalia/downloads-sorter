@echo off
setlocal DisableDelayedExpansion
set "DOWNLOADS_SORTER_LAUNCHER=%~f0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sort-downloads.ps1" %*
set "result=%errorlevel%"
if "%~1"=="" pause
exit /b %result%
