# Database Troubleshooting Guide

This guide helps you diagnose and resolve common database-related issues in wn-dl.

## Quick Diagnostics

### Check Database Status

```bash
# Verify database is enabled and accessible
wn-dl novels stats

# Check if database file exists
ls -la ~/.wn-dl/novels.db

# Test database connectivity
wn-dl novels list --limit 1
```

### Common Error Messages

| Error Message | Likely Cause | Solution |
|---------------|--------------|----------|
| "Database is locked" | Another process using database | Close other wn-dl instances |
| "No such table: novels" | Database not initialized | Run `wn-dl novels sync` |
| "Database is not enabled" | Database disabled in config | Enable in user preferences |
| "Permission denied" | File permission issues | Check file ownership/permissions |
| "Disk full" | No space for database operations | Free up disk space |

## Detailed Troubleshooting

### Database Connection Issues

#### Symptom: "Database is locked" Error

**Diagnosis Steps:**
1. Check for running wn-dl processes: `ps aux | grep wn-dl`
2. Verify database file permissions: `ls -la ~/.wn-dl/novels.db`
3. Check disk space: `df -h ~/.wn-dl/`

**Solutions:**
```bash
# Kill any hanging processes
pkill -f wn-dl

# Fix permissions (if needed)
chmod 644 ~/.wn-dl/novels.db
chown $USER:$USER ~/.wn-dl/novels.db

# Restart with fresh connection
wn-dl novels stats
```

#### Symptom: "No such file or directory" Error

**Diagnosis:**
- Database file doesn't exist
- Incorrect database path in configuration

**Solutions:**
```bash
# Create database directory
mkdir -p ~/.wn-dl

# Initialize database
wn-dl novels sync

# Or specify custom path in config
```

### Performance Issues

#### Symptom: Slow Database Operations

**Diagnosis Steps:**
1. Check database size: `ls -lh ~/.wn-dl/novels.db`
2. Monitor system resources during operations
3. Check for large number of records: `wn-dl novels stats`

**Solutions:**
```bash
# Optimize database
python3 -c "
from wn_dl.core.novel_database_service import NovelDatabaseService
db = NovelDatabaseService()
db.optimize_database()
db.close()
"

# Clean up old records
python3 -c "
from wn_dl.core.novel_database_service import NovelDatabaseService
db = NovelDatabaseService()
cleaned = db.cleanup_old_records(days_old=180)
print(f'Cleaned {cleaned} old records')
db.close()
"

# Cleanup orphaned records
wn-dl novels sync --cleanup
```

#### Symptom: High Memory Usage

**Diagnosis:**
- Large result sets being loaded into memory
- Memory leaks in long-running operations

**Solutions:**
```bash
# Use pagination for large collections
wn-dl novels list --limit 50

# Filter results to reduce memory usage
wn-dl novels list --status completed --limit 20

# Restart application periodically for long operations
```

### Data Integrity Issues

#### Symptom: Missing Novel Records

**Diagnosis Steps:**
1. Check if novels exist on filesystem: `ls /path/to/novels/`
2. Verify database has records: `wn-dl novels list`
3. Check sync status: `wn-dl novels stats`

**Solutions:**
```bash
# Sync filesystem to database
wn-dl novels sync -d /path/to/your/novels

# Force full resync
wn-dl novels sync --cleanup

# Check results
wn-dl novels stats
```

#### Symptom: Duplicate Records

**Diagnosis:**
- Multiple records for same novel URL
- Database constraint violations

**Solutions:**
```python
# Manual cleanup script
from wn_dl.core.novel_database_service import NovelDatabaseService

db = NovelDatabaseService()
with db.get_session() as session:
    # Find duplicates by URL
    from sqlalchemy import func
    from wn_dl.core.database_models import NovelRecord
    
    duplicates = session.query(NovelRecord.source_url, func.count(NovelRecord.id))\
        .group_by(NovelRecord.source_url)\
        .having(func.count(NovelRecord.id) > 1)\
        .all()
    
    for url, count in duplicates:
        print(f"Found {count} duplicates for {url}")
        # Keep the most recent record
        records = session.query(NovelRecord)\
            .filter_by(source_url=url)\
            .order_by(NovelRecord.updated_at.desc())\
            .all()
        
        # Delete older duplicates
        for record in records[1:]:
            session.delete(record)
    
    session.commit()
db.close()
```

### Backup and Recovery Issues

#### Symptom: Backup Creation Fails

**Diagnosis Steps:**
1. Check disk space: `df -h`
2. Verify write permissions: `touch ~/.wn-dl/test && rm ~/.wn-dl/test`
3. Check database file accessibility

**Solutions:**
```bash
# Create backup with explicit path
wn-dl novels backup -o /tmp/novels_backup.db

# Check backup file
ls -la /tmp/novels_backup.db

# Test backup integrity
sqlite3 /tmp/novels_backup.db "SELECT COUNT(*) FROM novels;"
```

#### Symptom: Restore Operation Fails

**Diagnosis:**
- Corrupted backup file
- Permission issues
- Database in use

**Solutions:**
```bash
# Verify backup file integrity
sqlite3 backup_file.db "PRAGMA integrity_check;"

# Ensure no processes are using database
pkill -f wn-dl

# Restore with explicit confirmation
wn-dl novels restore backup_file.db --confirm

# Verify restoration
wn-dl novels stats
```

### Configuration Issues

#### Symptom: "Database is not enabled" Message

**Diagnosis:**
- Database disabled in user configuration
- Configuration file not found

**Solutions:**
```bash
# Check current configuration
python3 -c "
from wn_dl.core.user_config import get_user_preferences
prefs = get_user_preferences()
print(f'Database enabled: {prefs.enable_database}')
print(f'Database path: {prefs.database_path}')
"

# Enable database in configuration
python3 -c "
from wn_dl.core.user_config import set_user_preference
set_user_preference('database.enabled', True)
print('Database enabled')
"
```

#### Symptom: Custom Database Path Not Working

**Diagnosis:**
- Incorrect path format in configuration
- Path doesn't exist or isn't writable

**Solutions:**
```bash
# Check configuration
cat ~/.config/wn-dl/config.yaml | grep -A5 database

# Test custom path
mkdir -p /custom/path/
touch /custom/path/test.db && rm /custom/path/test.db

# Update configuration
python3 -c "
from wn_dl.core.user_config import set_user_preference
set_user_preference('database.path', '/custom/path/novels.db')
"
```

## Recovery Procedures

### Complete Database Recovery

When database is completely corrupted or lost:

```bash
#!/bin/bash
# Complete database recovery script

echo "Starting complete database recovery..."

# 1. Backup any existing database
if [ -f ~/.wn-dl/novels.db ]; then
    cp ~/.wn-dl/novels.db ~/.wn-dl/novels.db.backup.$(date +%Y%m%d_%H%M%S)
    echo "Backed up existing database"
fi

# 2. Remove corrupted database
rm -f ~/.wn-dl/novels.db
echo "Removed corrupted database"

# 3. Recreate from filesystem
echo "Recreating database from filesystem..."
wn-dl novels sync -d /path/to/your/novels

# 4. Verify recovery
echo "Verifying recovery..."
wn-dl novels stats

echo "Recovery complete!"
```

### Partial Data Recovery

For recovering specific missing data:

```python
#!/usr/bin/env python3
# Partial data recovery script

from wn_dl.core.novel_database_service import NovelDatabaseService
from wn_dl.core.novel_discovery import NovelDiscoveryService
from pathlib import Path

def recover_missing_novels(novels_directory):
    """Recover novels that exist on filesystem but not in database."""
    
    db_service = NovelDatabaseService()
    discovery_service = NovelDiscoveryService(novels_directory)
    
    # Get novels from filesystem
    filesystem_novels = discovery_service._discover_novels_from_filesystem(Path(novels_directory))
    
    # Get novels from database
    db_novels = db_service.list_novels()
    db_paths = {novel.directory_path for novel in db_novels}
    
    # Find missing novels
    missing_novels = []
    for novel in filesystem_novels:
        if str(novel.directory) not in db_paths:
            missing_novels.append(novel)
    
    print(f"Found {len(missing_novels)} novels missing from database")
    
    # Add missing novels to database
    for novel in missing_novels:
        try:
            # Create basic metadata from filesystem info
            from wn_dl.core.models import NovelMetadata
            metadata = NovelMetadata(
                title=novel.title,
                author=novel.author,
                description=novel.description or "",
                source_url=f"file://{novel.directory}",
                chapter_count=novel.chapter_count
            )
            
            db_service.create_novel(metadata, str(novel.directory))
            print(f"Recovered: {novel.title}")
            
        except Exception as e:
            print(f"Failed to recover {novel.title}: {e}")
    
    db_service.close()
    print("Recovery complete!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python3 recover_novels.py /path/to/novels")
        sys.exit(1)
    
    recover_missing_novels(sys.argv[1])
```

## Prevention

### Regular Maintenance

Set up regular maintenance to prevent issues:

```bash
#!/bin/bash
# Weekly maintenance script

echo "Starting weekly database maintenance..."

# Sync with filesystem
wn-dl novels sync --cleanup

# Create backup
wn-dl novels backup -o ~/backups/novels_weekly_$(date +%Y%m%d).db

# Optimize database
python3 -c "
from wn_dl.core.novel_database_service import NovelDatabaseService
db = NovelDatabaseService()
db.optimize_database()
db.close()
print('Database optimized')
"

# Clean old backups (keep last 4 weeks)
find ~/backups/ -name "novels_weekly_*.db" -mtime +28 -delete

echo "Maintenance complete!"
```

### Monitoring

Monitor database health:

```python
#!/usr/bin/env python3
# Database health monitor

from wn_dl.core.novel_database_service import NovelDatabaseService
import os

def check_database_health():
    """Check database health and report issues."""
    
    db_service = NovelDatabaseService()
    
    try:
        # Check basic connectivity
        stats = db_service.get_statistics()
        print(f"✓ Database accessible: {stats['total_novels']} novels")
        
        # Check database size
        db_size = db_service.get_database_size()
        print(f"✓ Database size: {db_size / 1024 / 1024:.1f} MB")
        
        # Check for orphaned records
        orphaned = db_service.cleanup_orphaned_records()
        if orphaned > 0:
            print(f"⚠ Found {orphaned} orphaned records (cleaned up)")
        else:
            print("✓ No orphaned records found")
        
        # Check recent activity
        if stats['recent_updates'] == 0:
            print("⚠ No recent database updates (last 7 days)")
        else:
            print(f"✓ Recent activity: {stats['recent_updates']} updates")
        
        print("Database health check complete!")
        
    except Exception as e:
        print(f"✗ Database health check failed: {e}")
        return False
    
    finally:
        db_service.close()
    
    return True

if __name__ == "__main__":
    check_database_health()
```

## Getting Help

If you continue to experience database issues:

1. **Check logs** with debug logging enabled
2. **Create a minimal reproduction** case
3. **Backup your database** before trying fixes
4. **Report issues** with:
   - Error messages
   - Database statistics output
   - System information
   - Steps to reproduce

### Debug Information Collection

```bash
#!/bin/bash
# Collect debug information

echo "=== wn-dl Database Debug Information ===" > debug_info.txt
echo "Date: $(date)" >> debug_info.txt
echo "System: $(uname -a)" >> debug_info.txt
echo "" >> debug_info.txt

echo "=== Database File Info ===" >> debug_info.txt
ls -la ~/.wn-dl/novels.db >> debug_info.txt 2>&1
echo "" >> debug_info.txt

echo "=== Database Statistics ===" >> debug_info.txt
wn-dl novels stats >> debug_info.txt 2>&1
echo "" >> debug_info.txt

echo "=== Configuration ===" >> debug_info.txt
python3 -c "
from wn_dl.core.user_config import get_user_preferences
prefs = get_user_preferences()
print(f'Database enabled: {prefs.enable_database}')
print(f'Database path: {prefs.database_path}')
print(f'Auto sync: {prefs.auto_sync_filesystem}')
" >> debug_info.txt 2>&1

echo "Debug information saved to debug_info.txt"
```
