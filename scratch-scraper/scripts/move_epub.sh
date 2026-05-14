#!/bin/bash

# === Configuration ===
#
# 1. Set the directory you want to search for EPUB files.
#    Using "." will search from the directory where the script is run.
#    Example: SOURCE_DIR="/home/user/downloads"
SOURCE_DIR="/home/sugeng/novels"

# 2. Set the destination directory where all EPUB files will be moved.
#    This directory will be created if it doesn't already exist.
#    Example: DEST_DIR="/home/user/documents/ebooks"
DEST_DIR="/home/sugeng/epub_collection"
# === End of Configuration ===


# --- Script Logic (No need to edit below this line) ---

# Check if the source directory actually exists.
if [ ! -d "$SOURCE_DIR" ]; then
  echo "Error: Source directory '$SOURCE_DIR' does not exist."
  exit 1
fi

# Create the destination directory if it doesn't exist.
# The '-p' flag ensures that no error is reported if the directory already exists.
echo "Ensuring destination directory '$DEST_DIR' exists..."
mkdir -p "$DEST_DIR"

# Find all files ending with .epub (case-insensitive) in the source directory
# and its subdirectories, then move them to the destination directory.
#
# Explanation of the 'find' command:
#   "$SOURCE_DIR"   : The starting point for the search.
#   -type f         : Only find items that are files.
#   -iname "*.epub" : Find files with the .epub extension, ignoring case (matches .epub, .EPUB, etc.).
#   -exec mv -t ... : For each file found, execute the 'mv' command.
#     -t "$DEST_DIR" : Specifies the target directory for the move. This is a robust way to set the destination.
#     {} +           : Replaces '{}' with the list of found files. The '+' is efficient because it
#                      groups many files into a single 'mv' command, rather than running 'mv' for every file.
echo "Searching for .epub files in '$SOURCE_DIR' and moving them to '$DEST_DIR'..."
find "$SOURCE_DIR" -type f -iname "*.epub" -exec mv -t "$DEST_DIR" {} +

echo "Operation complete. All EPUB files have been moved."
