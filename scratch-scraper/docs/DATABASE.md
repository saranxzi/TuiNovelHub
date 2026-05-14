# Database Integration Guide

This guide covers the persistent storage features in wn-dl, including configuration, usage, and maintenance.

## Overview

wn-dl includes an optional persistent storage system that tracks novel metadata, scraping progress, and file locations. This enables:

- **Progress Tracking**: Monitor scraping status and resume interrupted downloads
- **Novel Management**: Search, filter, and organize your novel collection
- **Metadata Storage**: Preserve novel information even if files are moved
- **Statistics**: View collection statistics and scraping history

## Configuration

### Enabling Database Storage

Database storage is enabled by default. To configure it, edit your user configuration file:

```yaml
preferences:
  database:
    enabled: true                    # Enable/disable database storage
    path: null                       # Custom database path (null = default)
    auto_sync: true                  # Automatically sync with filesystem
    backup_enabled: true             # Enable automatic backups
```

### Default Database Location

If no custom path is specified, the database is stored at:
- **Linux/macOS**: `~/.wn-dl/novels.db`
- **Windows**: `%APPDATA%\wn-dl\novels.db`

### Custom Database Path

To use a custom database location:

```yaml
preferences:
  database:
    path: "/path/to/your/novels.db"
```

## Usage

### Automatic Integration

When database storage is enabled, wn-dl automatically:

1. **Creates records** when scraping new novels
2. **Updates progress** during chapter downloads
3. **Tracks status** (not started, in progress, completed, failed)
4. **Stores file paths** for markdown and EPUB files
5. **Records metadata** including title, author, genres, etc.

### CLI Commands

#### List Novels with Database Filtering

```bash
# List all novels
wn-dl novels list

# Filter by scraping status
wn-dl novels list --status completed
wn-dl novels list --status in_progress
wn-dl novels list --status failed

# Filter by provider
wn-dl novels list --provider NovelFull

# Search novels
wn-dl novels list --search "dragon"

# Show only novels without EPUB files
wn-dl novels list --no-epub

# Limit results
wn-dl novels list --limit 10
```

#### Database Maintenance

```bash
# Sync database with filesystem
wn-dl novels sync

# Sync and cleanup orphaned records
wn-dl novels sync --cleanup

# View database statistics
wn-dl novels stats

# Create database backup
wn-dl novels backup

# Create backup with custom filename
wn-dl novels backup -o my_backup.db

# Restore from backup
wn-dl novels restore backup_file.db
```

## Database Schema

### Novel Records

Each novel is stored with the following information:

| Field | Type | Description |
|-------|------|-------------|
| id | Integer | Primary key |
| title | String | Novel title |
| author | String | Author name |
| source_url | String | Original URL (unique) |
| provider | String | Source provider (NovelFull, etc.) |
| directory_path | String | Local directory path |
| markdown_file_path | String | Path to markdown file |
| epub_file_path | String | Path to EPUB file |
| cover_file_path | String | Path to cover image |
| description | Text | Novel description |
| genres | JSON | List of genres |
| tags | JSON | List of tags |
| novel_status | String | Novel status (ongoing, completed, etc.) |
| scraping_status | String | Scraping status (not_started, in_progress, etc.) |
| total_chapters | Integer | Total number of chapters |
| completed_chapters | Integer | Number of chapters scraped |
| last_chapter_scraped | Integer | Last chapter number scraped |
| word_count | Integer | Estimated word count |
| rating | Float | Novel rating |
| created_at | DateTime | Record creation time |
| updated_at | DateTime | Last update time |
| last_scraped_at | DateTime | Last scraping time |
| has_epub | Boolean | Whether EPUB file exists |
| has_cover | Boolean | Whether cover image exists |
| is_favorite | Boolean | User favorite flag |
| is_archived | Boolean | Archived status |

## Performance

### Database Indexes

The following indexes are automatically created for optimal performance:

- `idx_novels_status_updated`: Scraping status + update time
- `idx_novels_provider_status`: Provider + scraping status
- `idx_novels_title_author`: Title + author (for searching)
- `idx_novels_last_scraped`: Last scraped time
- `idx_novels_has_epub`: EPUB availability
- `idx_novels_directory_path`: Directory path

### Query Optimization

- Use specific filters when listing novels
- Limit results for large collections
- Regular database optimization (automatic)

## Maintenance

### Automatic Maintenance

wn-dl performs automatic maintenance:

- **WAL Mode**: Enabled for better concurrency
- **Pragma Settings**: Optimized for performance
- **Connection Pooling**: Efficient connection management

### Manual Maintenance

#### Sync with Filesystem

Synchronize database records with actual files:

```bash
# Sync current directory
wn-dl novels sync

# Sync specific directory
wn-dl novels sync -d /path/to/novels

# Sync and cleanup orphaned records
wn-dl novels sync --cleanup
```

#### Database Optimization

The database is automatically optimized, but you can trigger manual optimization:

```python
from wn_dl.core.novel_database_service import NovelDatabaseService

db_service = NovelDatabaseService()
db_service.optimize_database()
```

#### Cleanup Old Records

Remove old, failed records:

```python
# Remove records older than 1 year that failed and have no EPUB
cleaned_count = db_service.cleanup_old_records(days_old=365)
```

### Backup and Recovery

#### Automatic Backups

When `backup_enabled` is true, wn-dl creates automatic backups before major operations.

#### Manual Backups

```bash
# Create backup with timestamp
wn-dl novels backup

# Create backup with custom name
wn-dl novels backup -o novels_backup_2024.db
```

#### Restore from Backup

```bash
# Restore from backup (with confirmation)
wn-dl novels restore novels_backup_2024.db

# Restore without confirmation prompt
wn-dl novels restore novels_backup_2024.db --confirm
```

## Troubleshooting

### Common Issues

#### Database Locked Error

**Symptom**: "Database is locked" error during operations

**Solutions**:
1. Ensure no other wn-dl processes are running
2. Check file permissions on database file
3. Restart and try again
4. If persistent, restore from backup

#### Corrupted Database

**Symptom**: SQLite errors or unexpected behavior

**Solutions**:
1. Restore from recent backup
2. Recreate database and sync from filesystem
3. Check disk space and file system integrity

#### Performance Issues

**Symptom**: Slow database operations

**Solutions**:
1. Run database optimization: `db_service.optimize_database()`
2. Clean up old records: `db_service.cleanup_old_records()`
3. Check available disk space
4. Consider moving database to faster storage

#### Missing Records

**Symptom**: Novels not appearing in database

**Solutions**:
1. Run filesystem sync: `wn-dl novels sync`
2. Check database is enabled in configuration
3. Verify file permissions
4. Check logs for error messages

### Recovery Procedures

#### Complete Database Recovery

If the database is completely corrupted:

1. **Backup current database** (even if corrupted)
2. **Delete corrupted database file**
3. **Run filesystem sync** to recreate from files
4. **Restore metadata** from backups if available

```bash
# Backup corrupted database
cp ~/.wn-dl/novels.db ~/.wn-dl/novels.db.corrupted

# Remove corrupted database
rm ~/.wn-dl/novels.db

# Recreate from filesystem
wn-dl novels sync -d /path/to/your/novels
```

#### Partial Data Recovery

For partial corruption or missing records:

```bash
# Sync to recover missing records
wn-dl novels sync --cleanup

# Check statistics to verify recovery
wn-dl novels stats
```

### Logging and Debugging

Enable debug logging to troubleshoot database issues:

```yaml
preferences:
  logging:
    level: "DEBUG"
```

Check logs for database-related messages:
- Connection issues
- Query performance
- Backup/restore operations
- Sync operations

## Migration

### Schema Updates

Database schema updates are handled automatically. When wn-dl detects an older schema version, it will:

1. Create a backup of the current database
2. Apply necessary schema migrations
3. Verify data integrity
4. Update schema version

### Data Migration

When upgrading from filesystem-only to database storage:

1. Enable database in configuration
2. Run initial sync: `wn-dl novels sync`
3. Verify all novels are detected: `wn-dl novels list`
4. Check statistics: `wn-dl novels stats`

## Best Practices

### Configuration

- Keep database enabled for better novel management
- Use default database location unless you have specific needs
- Enable automatic backups
- Set up regular sync operations

### Maintenance

- Run `wn-dl novels sync` periodically to keep database current
- Create manual backups before major operations
- Monitor database size and performance
- Clean up old, failed records occasionally

### Performance

- Use specific filters when listing large collections
- Limit results for better performance
- Keep database file on fast storage (SSD)
- Monitor disk space usage

### Backup Strategy

- Enable automatic backups in configuration
- Create manual backups before major changes
- Store backups in different location than database
- Test backup restoration periodically
