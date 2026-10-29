@if (@X)==(@Y) @end /*
@echo off
setlocal DisableDelayedExpansion
set "DOWNLOADS_SORTER_LAUNCHER=%~f0"
cscript.exe //E:JScript //nologo "%~f0" %*
set "result=%errorlevel%"
if "%~1"=="" pause
exit /b %result%
*/
// Windows Script Host JScript, ES3 syntax for Windows XP and later.
(function () {
    var fso = new ActiveXObject("Scripting.FileSystemObject");
    var home = fso.GetParentFolderName(WScript.ScriptFullName);
    var launcher = new ActiveXObject("WScript.Shell").Environment("PROCESS")("DOWNLOADS_SORTER_LAUNCHER");
    var root = home, apply = true, a = WScript.Arguments, i;
    try {
        for (i = 0; i < a.length; i++) {
            if (a(i) === "--apply") { apply = true; }
            else if (a(i) === "--dry-run") { apply = false; }
            else if (a(i) === "--help") {
                WScript.Echo("Usage: sort-downloads-legacy.bat [--path FOLDER] [--dry-run | --apply] (default: move files)");
                WScript.Quit(0);
            } else if (a(i) === "--path") {
                i++;
                if (i >= a.length) { throw new Error("--path requires a folder"); }
                root = a(i);
            } else { throw new Error("Unknown argument: " + a(i)); }
        }
        root = fso.GetAbsolutePathName(root);
        if (!fso.FolderExists(root)) { throw new Error("Target must be a directory"); }
        // FSO preserves aliases in Path: compare both identities in ShortPath form.
        var scriptId = fso.GetFile(WScript.ScriptFullName).ShortPath.toLowerCase();
        var launcherId = launcher ? fso.GetFile(launcher).ShortPath.toLowerCase() : "";
        // Embedded category table; no runtime sidecar is required.
        var text = "archives zip gz tgz rar 7z tar bz2 xz cab arj lzh ace 001 zst bz z lz lzma txz tbz2\niso iso img bin cue nrg mdf mds vcd dmg vhd vhdx vdi qcow2\nmusic mp3 wav flac aac ogg wma m4a aiff aif alac ape pls m3u m3u8 aimppl opus mid midi\nvideo avi mov mp4 mkv 3gp webm flv wmv mpeg mpg vob m4v ts mts m2ts divx f4v\nprograms exe msi msix appx apk pkg bat sh deb rpm jar py com cmd scr ps1 command appimage\nphotos jpg jpeg jpe heic heif cr2 cr3 nef arw dng raw orf rw2 srw tif tiff pef bay raf\nimages png bmp gif svg webp ico psd ai xcf emf wmf dds jpf jpx avif jxl eps\ndocs pdf txt doc docx xls xlsx ods rtf odt ppt pptx csv djvu epub fb2 md tex log mobi azw azw3 odp ics";
        var lines = text.split(/\r?\n/), map = {}, parts, j, category;
        for (i = 0; i < lines.length; i++) {
            if (!/\S/.test(lines[i])) { continue; }
            parts = lines[i].replace(/^\s+|\s+$/g, "").split(/\s+/);
            category = parts[0];
            if (parts.length < 2 || !/^[a-z]+$/.test(category)) { throw new Error("Invalid embedded category table"); }
            for (j = 1; j < parts.length; j++) {
                if (!/^[a-z0-9]+$/.test(parts[j]) || map["ext:" + parts[j]]) { throw new Error("Invalid or duplicate extension"); }
                map["ext:" + parts[j]] = category;
            }
        }
        // Snapshot before moving: do not mutate an active FSO enumerator.
        var files = [], enumeration = new Enumerator(fso.GetFolder(root).Files);
        for (; !enumeration.atEnd(); enumeration.moveNext()) { files.push(enumeration.item().Path); }
        var moved = 0, planned = 0, errors = 0, src, name, ext, folder, dest;
        for (i = 0; i < files.length; i++) {
            src = files[i];
            var sourceFile = fso.GetFile(src), sourceId = sourceFile.ShortPath.toLowerCase();
            if ((sourceFile.Attributes & 1024) || sourceId === scriptId || sourceId === launcherId) { continue; }
            name = fso.GetFileName(src);
            if ("|sort-downloads.py|sort-downloads.bat|sort-downloads.ps1|sort-downloads-legacy.bat|sort-downloads-legacy.js|sort-downloads.sh|sort downloads.command|categories.txt|readme.md|license|".indexOf("|" + name.toLowerCase() + "|") >= 0) { continue; }
            ext = fso.GetExtensionName(name).toLowerCase();
            category = map["ext:" + ext];
            if (!category) { continue; }
            folder = fso.BuildPath(root, category);
            if (fso.FileExists(folder) || (fso.FolderExists(folder) && (fso.GetFolder(folder).Attributes & 1024))) {
                errors++; WScript.Echo("ERROR: Unsafe category directory: " + folder); continue;
            }
            dest = fso.BuildPath(folder, name);
            if (fso.FileExists(dest) || fso.FolderExists(dest)) { WScript.Echo("SKIP exists: " + dest); continue; }
            planned++;
            if (!apply) { WScript.Echo("PLAN: " + src + " -> " + dest); continue; }
            try {
                if (!fso.FolderExists(folder)) { fso.CreateFolder(folder); }
                fso.MoveFile(src, dest); // FSO never overwrites an existing file.
                moved++;
                WScript.Echo("MOVED: " + name + " -> " + category);
            } catch (e) { errors++; WScript.Echo("ERROR: " + e.message); }
        }
        WScript.Echo("Done. Planned=" + planned + " Moved=" + moved + " Errors=" + errors + " Apply=" + apply);
        WScript.Quit(errors ? 1 : 0);
    } catch (e) { WScript.Echo("ERROR: " + e.message); WScript.Quit(2); }
}());
