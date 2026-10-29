// Windows Script Host JScript, ES3 syntax for Windows XP and later.
(function () {
    var fso = new ActiveXObject("Scripting.FileSystemObject");
    var home = fso.GetParentFolderName(WScript.ScriptFullName);
    var launcher = new ActiveXObject("WScript.Shell").Environment("PROCESS")("DOWNLOADS_SORTER_LAUNCHER");
    var root = home, apply = false, a = WScript.Arguments, i;
    try {
        for (i = 0; i < a.length; i++) {
            if (a(i) === "--apply") { apply = true; }
            else if (a(i) === "--dry-run") { apply = false; }
            else if (a(i) === "--help") {
                WScript.Echo("Usage: sort-downloads-legacy.bat [--path FOLDER] [--dry-run | --apply]");
                WScript.Quit(0);
            } else if (a(i) === "--path") {
                i++;
                if (i >= a.length) { throw new Error("--path requires a folder"); }
                root = a(i);
            } else { throw new Error("Unknown argument: " + a(i)); }
        }
        root = fso.GetAbsolutePathName(root);
        if (!fso.FolderExists(root)) { throw new Error("Target must be a directory"); }
        var stream = fso.OpenTextFile(fso.BuildPath(home, "categories.txt"), 1, false, 0);
        var text = stream.ReadAll();
        stream.Close();
        var lines = text.split(/\r?\n/), map = {}, parts, j, category;
        for (i = 0; i < lines.length; i++) {
            if (!/\S/.test(lines[i])) { continue; }
            parts = lines[i].replace(/^\s+|\s+$/g, "").split(/\s+/);
            category = parts[0];
            if (parts.length < 2 || !/^[a-z]+$/.test(category)) { throw new Error("Invalid categories.txt"); }
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
            if ((fso.GetFile(src).Attributes & 1024) || src.toLowerCase() === WScript.ScriptFullName.toLowerCase() ||
                src.toLowerCase() === launcher.toLowerCase()) { continue; }
            name = fso.GetFileName(src);
            if ("|sort-downloads.bat|sort-downloads.ps1|sort-downloads-legacy.bat|sort-downloads-legacy.js|sort-downloads.sh|sort downloads.command|categories.txt|readme.md|license|".indexOf("|" + name.toLowerCase() + "|") >= 0) { continue; }
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
