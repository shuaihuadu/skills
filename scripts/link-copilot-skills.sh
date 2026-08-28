#!/bin/sh

set -eu

usage() {
    cat <<'EOF'
Usage:
  link-copilot-skills.sh [--target PATH] [--force] SOURCE

Creates a symbolic link from Copilot's personal Skills directory to SOURCE.
The default target is ~/.copilot/skills.

Options:
  --target PATH  Override the Copilot Skills target directory.
  --force        Back up an existing target before creating the link.
  -h, --help     Show this help message.
EOF
}

source_dir=""
target_dir="$HOME/.copilot/skills"
force=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --target)
            if [ "$#" -lt 2 ]; then
                echo "Error: --target requires a path." >&2
                exit 2
            fi
            target_dir=$2
            shift 2
            ;;
        --force)
            force=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        --*)
            echo "Error: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
        *)
            if [ -n "$source_dir" ]; then
                echo "Error: only one SOURCE directory may be specified." >&2
                usage >&2
                exit 2
            fi
            source_dir=$1
            shift
            ;;
    esac
done

if [ -z "$source_dir" ]; then
    echo "Error: SOURCE is required." >&2
    usage >&2
    exit 2
fi

case "$source_dir" in
    "~") source_dir=$HOME ;;
    "~/"*) source_dir="$HOME/${source_dir#\~/}" ;;
esac
case "$target_dir" in
    "~") target_dir=$HOME ;;
    "~/"*) target_dir="$HOME/${target_dir#\~/}" ;;
esac

if [ ! -d "$source_dir" ]; then
    echo "Error: source directory does not exist: $source_dir" >&2
    exit 1
fi

source_dir=$(cd "$source_dir" && pwd -P)

has_skill=0
for skill_file in "$source_dir"/*/SKILL.md; do
    if [ -f "$skill_file" ]; then
        has_skill=1
        break
    fi
done
if [ "$has_skill" -ne 1 ]; then
    echo "Error: source must contain at least one <skill-name>/SKILL.md file." >&2
    exit 1
fi

target_parent=$(dirname "$target_dir")
mkdir -p "$target_parent"
target_parent=$(cd "$target_parent" && pwd -P)
target_dir="$target_parent/$(basename "$target_dir")"

if [ "$target_dir" = "$source_dir" ]; then
    echo "Error: source and target directories must be different." >&2
    exit 1
fi

if [ -L "$target_dir" ] && [ -d "$target_dir" ]; then
    existing_source=$(cd "$target_dir" && pwd -P)
    if [ "$existing_source" = "$source_dir" ]; then
        echo "Copilot Skills is already linked to: $source_dir"
        exit 0
    fi
fi

if [ -e "$target_dir" ] || [ -L "$target_dir" ]; then
    if [ "$force" -ne 1 ]; then
        echo "Error: target already exists: $target_dir" >&2
        echo "Run again with --force to back it up before linking." >&2
        exit 1
    fi

    backup_path="$target_dir.backup.$(date +%Y%m%d-%H%M%S)"
    mv "$target_dir" "$backup_path"
    echo "Existing target backed up to: $backup_path"
fi

ln -s "$source_dir" "$target_dir"

echo "Copilot Skills link created:"
echo "  $target_dir -> $source_dir"
echo "Reload the VS Code window and start a new Copilot Chat session."
