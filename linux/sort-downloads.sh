#!/bin/bash
# Bash 3.2+; compatible with stock macOS and Linux. No Python dependency.
export LC_ALL=C
script_dir=${BASH_SOURCE[0]%/*}
[ "$script_dir" != "${BASH_SOURCE[0]}" ] || script_dir=.
[ -n "$script_dir" ] || script_dir=/
# A sentinel prevents command substitution from stripping path newlines.
home=$(CDPATH= cd -P -- "$script_dir" && printf '%s.' "$PWD") || exit 2
home=${home%.}
root=$home
apply=1
while [ "$#" -gt 0 ]; do
    case "$1" in
        --apply) apply=1; shift ;;
        --dry-run) apply=0; shift ;;
        --path) [ "$#" -ge 2 ] || { printf '%s\n' 'ERROR: --path requires a folder' >&2; exit 2; }
            root=$2; shift 2 ;;
        --help) printf '%s\n' 'Usage: sorter [--path FOLDER] [--dry-run | --apply] (default: move files)'; exit 0 ;;
        *) printf 'ERROR: Unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
done
root=$(CDPATH= cd -P -- "$root" && printf '%s.' "$PWD") || exit 2
root=${root%.}
# Embedded category table: this file is the complete runtime.
config='archives zip gz tgz rar 7z tar bz2 xz cab arj lzh ace 001 zst bz z lz lzma txz tbz2
iso iso img bin cue nrg mdf mds vcd dmg vhd vhdx vdi qcow2
music mp3 wav flac aac ogg wma m4a aiff aif alac ape pls m3u m3u8 aimppl opus mid midi
video avi mov mp4 mkv 3gp webm flv wmv mpeg mpg vob m4v ts mts m2ts divx f4v
programs exe msi msix appx apk pkg bat sh deb rpm jar py com cmd scr ps1 command appimage
photos jpg jpeg jpe heic heif cr2 cr3 nef arw dng raw orf rw2 srw tif tiff pef bay raf
images png bmp gif svg webp ico psd ai xcf emf wmf dds jpf jpx avif jxl eps
docs pdf txt doc docx xls xlsx ods rtf odt ppt pptx csv djvu epub fb2 md tex log mobi azw azw3 odp ics'
extensions=()
categories=()
while IFS=' ' read -r category rest || [ -n "$category" ]; do
    [ -n "$category" ] || continue
    [[ $category =~ ^[a-z]+$ && -n $rest ]] || { printf '%s\n' 'ERROR: Invalid embedded category table' >&2; exit 2; }
    IFS=' ' read -r -a tokens <<< "$rest"
    for ext in "${tokens[@]}"; do
        [[ $ext =~ ^[a-z0-9]+$ ]] || { printf '%s\n' 'ERROR: Invalid extension' >&2; exit 2; }
        for known in "${extensions[@]}"; do
            [ "$known" != "$ext" ] || { printf '%s\n' 'ERROR: Duplicate extension' >&2; exit 2; }
        done
        extensions[${#extensions[@]}]=$ext
        categories[${#categories[@]}]=$category
    done
done <<< "$config"
shopt -s nullglob dotglob
moved=0
planned=0
errors=0
for src in "$root"/*; do
    [ -f "$src" ] && [ ! -L "$src" ] || continue
    [ "$src" -ef "${BASH_SOURCE[0]}" ] && continue
    name=${src##*/}
    safe_name=$(printf '%s.' "$name" | tr '[:upper:]' '[:lower:]')
    safe_name=${safe_name%.}
    case "$safe_name" in
        'sort-downloads.py'|'sort-downloads.bat'|'sort-downloads.ps1'|'sort-downloads-legacy.bat'|'sort-downloads-legacy.js'|'sort-downloads.sh'|'sort downloads.command'|'categories.txt'|'readme.md'|'license') continue ;;
    esac
    case "$name" in *.*) ext=${name##*.} ;; *) continue ;; esac
    [[ $ext =~ ^[A-Za-z0-9]+$ ]] || continue
    ext=$(printf '%s' "$ext" | tr '[:upper:]' '[:lower:]')
    category=''
    for ((i=0; i<${#extensions[@]}; i++)); do
        if [ "${extensions[$i]}" = "$ext" ]; then category=${categories[$i]}; break; fi
    done
    [ -n "$category" ] || continue
    folder=$root/$category
    if [ -L "$folder" ] || { [ -e "$folder" ] && [ ! -d "$folder" ]; }; then
        errors=$((errors + 1))
        printf 'ERROR: Unsafe category directory: %s\n' "$folder" >&2
        continue
    fi
    dest=$folder/$name
    if [ -e "$dest" ] || [ -L "$dest" ]; then printf 'SKIP exists: %s\n' "$dest"; continue; fi
    planned=$((planned + 1))
    if [ "$apply" -eq 0 ]; then printf 'PLAN: %s -> %s\n' "$src" "$dest"; continue; fi
    if mkdir -p -- "$folder" && mv -n -- "$src" "$dest" && [ ! -e "$src" ]; then
        moved=$((moved + 1))
        printf 'MOVED: %s -> %s\n' "$name" "$category"
    else
        errors=$((errors + 1))
        printf 'ERROR: Could not move: %s\n' "$src" >&2
    fi
done
printf 'Done. Planned=%s Moved=%s Errors=%s Apply=%s\n' "$planned" "$moved" "$errors" "$apply"
[ "$errors" -eq 0 ]
