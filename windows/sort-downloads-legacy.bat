@echo off
setlocal DisableDelayedExpansion
set "DOWNLOADS_SORTER_LAUNCHER=%~f0"
cscript.exe //nologo "%~dp0sort-downloads-legacy.js" %*
set "result=%errorlevel%"
if "%~1"=="" pause
exit /b %result%
