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
apply=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --apply) apply=1; shift ;;
        --dry-run) apply=0; shift ;;
        --path) [ "$#" -ge 2 ] || { printf '%s\n' 'ERROR: --path requires a folder' >&2; exit 2; }
            root=$2; shift 2 ;;
        --help) printf '%s\n' 'Usage: sorter [--path FOLDER] [--dry-run | --apply]'; exit 0 ;;
        *) printf 'ERROR: Unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
done
root=$(CDPATH= cd -P -- "$root" && printf '%s.' "$PWD") || exit 2
root=${root%.}
[ -f "$home/categories.txt" ] && [ -r "$home/categories.txt" ] || { printf '%s\n' 'ERROR: Missing or unreadable categories.txt' >&2; exit 2; }
# Finish reading successfully before parsing or moving any file.
config=$(cat -- "$home/categories.txt" && printf '.') || { printf '%s\n' 'ERROR: Could not read categories.txt' >&2; exit 2; }
config=${config%.}
extensions=()
categories=()
while IFS=' ' read -r category rest || [ -n "$category" ]; do
    [ -n "$category" ] || continue
    [[ $category =~ ^[a-z]+$ && -n $rest ]] || { printf '%s\n' 'ERROR: Invalid categories.txt' >&2; exit 2; }
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
        'sort-downloads.bat'|'sort-downloads.ps1'|'sort-downloads-legacy.bat'|'sort-downloads-legacy.js'|'sort-downloads.sh'|'sort downloads.command'|'categories.txt'|'readme.md'|'license') continue ;;
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
