# Import Existing Novels Guide

This guide explains how to import existing novels from your filesystem into the wn-dl database without needing to re-scrape them.

## Overview

If you have existing novels downloaded before the database feature was implemented, you can import them into the database to take advantage of the new features like:

- Advanced search and filtering
- Progress tracking
- Status management
- Statistics and reporting

## Quick Start

### Using CLI Command (Recommended)

```bash
# Import novels from default directory (/home/sugeng/novels)
wn-dl novels import

# Import from custom directory
wn-dl novels import -d /path/to/your/novels

# Dry run to see what would be imported
wn-dl novels import --dry-run

# Force update existing records
wn-dl novels import --force-update
```

### Using Import Script

```bash
# Run the import script directly
python3 scripts/import_existing_novels.py

# Import from custom directory
python3 scripts/import_existing_novels.py /path/to/your/novels

# Dry run mode
python3 scripts/import_existing_novels.py --dry-run

# Verbose output
python3 scripts/import_existing_novels.py --verbose
```

## How It Works

### Novel Detection

The import process scans your directory structure looking for:

1. **Directories** that contain novel files
2. **Markdown files** (`.md`) with novel content
3. **EPUB files** (`.epub`) 
4. **Cover images** (`.jpg`, `.png`, etc.)

### Metadata Extraction

For each novel found, the importer:

1. **Extracts basic info** from directory and file names
2. **Reads YAML frontmatter** from markdown files (if present)
3. **Analyzes file structure** to determine chapter count and file sizes
4. **Creates database records** with all available information

### YAML Frontmatter Support

If your markdown files contain YAML frontmatter, the importer will extract rich metadata:

```yaml
---
title: "Novel Title"
author: "Author Name"
description: "Novel description"
source_url: "https://original-source.com/novel"
provider: "NovelFull"
status: "completed"
genres: ["Fantasy", "Adventure"]
tags: ["Magic", "Dragons"]
---

# Novel Content Starts Here
```

## Directory Structure

The importer expects novels to be organized in directories:

```
/home/sugeng/novels/
├── Novel Title 1/
│   ├── Novel Title 1.md
│   ├── Novel Title 1.epub
│   └── cover.jpg
├── Novel Title 2/
│   ├── Novel Title 2.md
│   └── Novel Title 2.epub
└── Novel Title 3/
    └── Novel Title 3.epub
```

## Import Options

### Dry Run Mode

Use `--dry-run` to see what would be imported without making changes:

```bash
wn-dl novels import --dry-run
```

This will show:
- How many novels were found
- Which novels would be imported vs. skipped
- Any potential errors

### Force Update

Use `--force-update` to update existing database records:

```bash
wn-dl novels import --force-update
```

This will:
- Update metadata for novels already in database
- Refresh file paths and sizes
- Update chapter counts and other statistics

### Custom Directory

Specify a different directory to import from:

```bash
wn-dl novels import -d /path/to/your/novels
```

## What Gets Imported

For each novel, the following information is stored in the database:

### Basic Information
- **Title** (from directory name or YAML)
- **Author** (from YAML or "Unknown")
- **Description** (from YAML if available)
- **Source URL** (from YAML or generated file:// URL)

### File Information
- **Directory path**
- **Markdown file path and size**
- **EPUB file path and size**
- **Cover image path**
- **File existence flags** (has_epub, has_cover)

### Metadata (if available in YAML)
- **Provider** (NovelFull, NovelBin, etc.)
- **Genres and tags**
- **Novel status** (completed, ongoing, etc.)
- **Chapter count**
- **Word count**

### Timestamps
- **Created date** (file creation time)
- **Import date** (when imported to database)

## Examples

### Basic Import

```bash
# Import all novels from default directory
$ wn-dl novels import

Importing novels from: /home/sugeng/novels
Found 25 novels to process
Processing novels... ████████████████████ 100%

✅ Import completed!
📚 Scanned: 25 novels
➕ Imported: 23 new novels
🔄 Updated: 0 existing novels
⏭️ Skipped: 2 novels
```

### Dry Run

```bash
# See what would be imported
$ wn-dl novels import --dry-run

DRY RUN MODE - No changes will be made
Importing novels from: /home/sugeng/novels
Found 25 novels to process

✅ Import completed!
📚 Scanned: 25 novels
➕ Imported: 25 new novels (would be imported)
🔄 Updated: 0 existing novels
⏭️ Skipped: 0 novels
```

### Force Update

```bash
# Update existing records
$ wn-dl novels import --force-update

Importing novels from: /home/sugeng/novels
Found 25 novels to process
Processing novels... ████████████████████ 100%

✅ Import completed!
📚 Scanned: 25 novels
➕ Imported: 0 new novels
🔄 Updated: 25 existing novels
⏭️ Skipped: 0 novels
```

## After Import

Once novels are imported, you can use all database features:

### List and Filter

```bash
# List all imported novels
wn-dl novels list

# Filter by provider
wn-dl novels list --provider "Imported"

# Search for specific novels
wn-dl novels list --search "dragon"

# Show only novels with EPUBs
wn-dl novels list | grep "✅"
```

### View Statistics

```bash
# Show database statistics
wn-dl novels stats
```

### Manage Database

```bash
# Create backup after import
wn-dl novels backup

# Sync with filesystem (if files change)
wn-dl novels sync
```

## Troubleshooting

### No Novels Found

If no novels are found:

1. **Check directory structure** - novels should be in subdirectories
2. **Verify file extensions** - look for `.md` or `.epub` files
3. **Check permissions** - ensure read access to directories
4. **Use verbose mode** - add `--verbose` for detailed logging

### Import Errors

Common issues and solutions:

| Error | Cause | Solution |
|-------|-------|----------|
| "Permission denied" | No read access | Check file permissions |
| "Database is locked" | Another process using DB | Close other wn-dl instances |
| "Invalid YAML" | Malformed frontmatter | Fix YAML syntax in markdown |
| "Directory not found" | Path doesn't exist | Verify directory path |

### Partial Import

If some novels fail to import:

1. **Check error messages** in the output
2. **Run with verbose logging** to see details
3. **Fix individual issues** (permissions, file format, etc.)
4. **Re-run import** - successfully imported novels will be skipped

### Duplicate Detection

The importer uses directory paths to detect duplicates:
- Novels with the same directory path are considered duplicates
- Use `--force-update` to update existing records
- Different directories with same title are treated as separate novels

## Advanced Usage

### Script Parameters

The standalone script supports additional options:

```bash
python3 scripts/import_existing_novels.py --help

usage: import_existing_novels.py [-h] [--dry-run] [--force-update] [--verbose] 
                                [--database-path DATABASE_PATH] [directory]

positional arguments:
  directory             Directory to scan for novels (default: /home/sugeng/novels)

optional arguments:
  -h, --help            show this help message and exit
  --dry-run             Show what would be imported without actually doing it
  --force-update        Update existing records even if they already exist
  --verbose, -v         Enable verbose logging
  --database-path DATABASE_PATH
                        Custom database path (uses user preference if not specified)
```

### Custom Database Path

```bash
# Use custom database
python3 scripts/import_existing_novels.py --database-path /path/to/custom.db
```

### Batch Processing

For large collections, you can process in batches:

```bash
# Import specific subdirectories
wn-dl novels import -d /novels/fantasy
wn-dl novels import -d /novels/scifi
wn-dl novels import -d /novels/romance
```

## Best Practices

1. **Backup first** - Create database backup before large imports
2. **Use dry run** - Always test with `--dry-run` first
3. **Organize files** - Keep novels in separate directories
4. **Add metadata** - Include YAML frontmatter for rich metadata
5. **Regular sync** - Run `wn-dl novels sync` periodically
6. **Monitor errors** - Check for and fix any import errors

## Integration with Existing Workflow

After importing existing novels:

1. **Verify import** - Check that all novels were imported correctly
2. **Update metadata** - Add missing information through YAML frontmatter
3. **Generate missing EPUBs** - Use `wn-dl generate-epub` for novels without EPUBs
4. **Set up regular sync** - Keep database current with filesystem changes
5. **Use new features** - Take advantage of search, filtering, and statistics

The import process is designed to be safe and non-destructive - it only reads your files and creates database records without modifying your existing novel files.
