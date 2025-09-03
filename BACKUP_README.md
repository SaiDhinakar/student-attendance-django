# MySQL Database Backup System

This document explains the automated MySQL database backup system for the Student Attendance Django project.

## 📋 Overview

The backup system automatically copies data from your main attendance database to a backup database on a configurable schedule. Unlike traditional file-based backups, this system:

- ✅ Maintains a live backup database with current data
- ✅ Copies all table structures and data efficiently
- ✅ Runs on a configurable schedule (default: daily at 2 AM)
- ✅ Provides health monitoring and logging
- ✅ Handles large databases with batch processing
- ✅ Automatically creates backup database if needed

## 🚀 Quick Start

### 1. Setup the Backup System

```bash
# Make the setup script executable and run it
chmod +x setup_backup.sh
./setup_backup.sh
```

This will:
- Install required dependencies (`mysql-connector-python`)
- Create the backup database if needed
- Set up automated cron job
- Configure logging
- Run initial health check

### 2. Verify Setup

```bash
# Check if backup system is working
python3 backup_manager.py health

# Run a test backup manually
python3 backup_manager.py run
```

## ⚙️ Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Backup Database Configuration
BACKUP_DATABASE_NAME=attendance_backup
BACKUP_SCHEDULE=0 2 * * *
BACKUP_BATCH_SIZE=1000
BACKUP_RETENTION_DAYS=30
BACKUP_NOTIFICATIONS_ENABLED=true
BACKUP_LOG_LEVEL=INFO
BACKUP_CONNECTION_TIMEOUT=1800
```

### Schedule Configuration

The `BACKUP_SCHEDULE` uses cron format: `minute hour day month dayofweek`

**Examples:**
- `0 2 * * *` - Daily at 2:00 AM (default)
- `0 3 * * 0` - Weekly on Sunday at 3:00 AM
- `0 1 1 * *` - Monthly on 1st day at 1:00 AM
- `0 */6 * * *` - Every 6 hours
- `30 14 * * *` - Daily at 2:30 PM

### Batch Size Configuration

- `BACKUP_BATCH_SIZE=1000` - Process 1000 rows at a time (default)
- Higher values = faster backup but more memory usage
- Lower values = slower backup but less memory usage

## 🔧 Usage

### Manual Commands

```bash
# Run immediate backup
python3 backup_manager.py run

# Start scheduled backup service (runs continuously)
python3 backup_manager.py schedule

# Check system health
python3 backup_manager.py health
```

### Django Management Command

```bash
# Use Django management command directly
python manage.py backup_database --verbose

# Force create backup database if it doesn't exist
python manage.py backup_database --force
```

## 📊 Monitoring

### Log Files

- **Main log**: `logs/backup.log` - Detailed backup process logs
- **Cron log**: `logs/backup_cron.log` - Automated backup execution logs

```bash
# View live backup logs
tail -f logs/backup.log

# View cron execution logs
tail -f logs/backup_cron.log
```

### Backup Status

Check the `backup_log` table in your backup database:

```sql
-- Connect to backup database
USE attendance_backup;

-- View recent backups
SELECT * FROM backup_log ORDER BY backup_timestamp DESC LIMIT 10;

-- Check backup frequency
SELECT 
    DATE(backup_timestamp) as backup_date,
    COUNT(*) as backup_count
FROM backup_log 
WHERE backup_timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(backup_timestamp)
ORDER BY backup_date DESC;
```

## 🗂️ Database Structure

### Main Database
- **Name**: `attendance_db` (your main database)
- **Contains**: All your live application data

### Backup Database
- **Name**: `attendance_backup` (configurable)
- **Contains**: 
  - Exact copy of all tables from main database
  - `backup_log` table for tracking backup history

### Backup Process

1. **Structure Copy**: Recreates all table structures in backup database
2. **Data Copy**: Copies all data in configurable batches
3. **Logging**: Records backup timestamp and status
4. **Cleanup**: Removes old backup logs based on retention settings

## 🛠️ Troubleshooting

### Common Issues

1. **"Module mysql.connector not found"**
   ```bash
   # Install the MySQL connector
   pip install mysql-connector-python
   ```

2. **"Backup database does not exist"**
   ```bash
   # Use force flag to create it
   python manage.py backup_database --force
   ```

3. **"Permission denied"**
   ```bash
   # Make sure files are executable
   chmod +x backup_manager.py setup_backup.sh
   ```

4. **Cron job not running**
   ```bash
   # Check if cron service is running
   sudo systemctl status cron
   
   # View current cron jobs
   crontab -l
   
   # Check cron logs
   tail -f /var/log/cron
   ```

### Health Check

Run a comprehensive health check:

```bash
python3 backup_manager.py health
```

This checks:
- ✅ Main database connectivity
- ✅ Backup database existence
- ✅ Available disk space
- ✅ Configuration validity

## 📈 Performance Considerations

### Large Databases

For databases with millions of records:

1. **Increase batch size**: `BACKUP_BATCH_SIZE=5000`
2. **Run during low traffic**: Schedule for 2-4 AM
3. **Monitor disk space**: Backup database needs same space as main
4. **Increase timeout**: `BACKUP_CONNECTION_TIMEOUT=3600` (1 hour)

### Memory Usage

- Each batch loads `BACKUP_BATCH_SIZE` rows into memory
- Typical usage: ~1MB per 1000 rows (varies by data)
- Adjust batch size based on available RAM

## 🔐 Security Notes

### Database Access

- Backup uses same credentials as main application
- Ensure MySQL user has permissions for:
  - `CREATE DATABASE`
  - `SELECT` on main database
  - `INSERT`, `DELETE`, `CREATE TABLE` on backup database

### File Permissions

```bash
# Secure configuration files
chmod 600 .env backup_config.env

# Secure backup scripts
chmod 750 backup_manager.py setup_backup.sh
```

## 🔄 Backup Recovery

### Restore from Backup

If you need to restore data from backup:

```sql
-- Example: Restore a specific table
DROP TABLE IF EXISTS attendance_db.core_student;
CREATE TABLE attendance_db.core_student LIKE attendance_backup.core_student;
INSERT INTO attendance_db.core_student SELECT * FROM attendance_backup.core_student;

-- Or restore all data (be very careful!)
-- This will overwrite all your main database data
-- mysqldump attendance_backup | mysql attendance_db
```

### Point-in-Time Recovery

The backup represents data as of the last backup time. For point-in-time recovery:

1. Use MySQL binary logs (if enabled)
2. Restore from backup to a specific timestamp
3. Apply binary logs from backup time to desired point

## 📅 Maintenance

### Regular Tasks

1. **Monitor logs weekly**
   ```bash
   tail -100 logs/backup.log | grep -i error
   ```

2. **Check disk space monthly**
   ```bash
   df -h | grep -E "(backup|mysql)"
   ```

3. **Test restore quarterly**
   - Restore a test table from backup
   - Verify data integrity

### Configuration Updates

After changing backup settings:

1. Update `.env` or `backup_config.env`
2. Re-run setup script: `./setup_backup.sh`
3. Test new configuration: `python3 backup_manager.py run`

## 🆘 Emergency Procedures

### Immediate Backup

If you need an urgent backup before scheduled time:

```bash
# Run immediate backup
python3 backup_manager.py run
```

### Stop Automatic Backups

```bash
# Remove cron job temporarily
crontab -l | grep -v "backup_manager.py" | crontab -

# To re-enable, run setup again
./setup_backup.sh
```

### Manual Database Backup

As a fallback, traditional MySQL dump:

```bash
# Create SQL dump backup
mysqldump -u root -p attendance_db > manual_backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from SQL dump
mysql -u root -p attendance_db < manual_backup_YYYYMMDD_HHMMSS.sql
```

## 📞 Support

If you encounter issues:

1. Check logs: `tail -f logs/backup.log`
2. Run health check: `python3 backup_manager.py health`
3. Verify configuration: Review `.env` file
4. Test manually: `python3 backup_manager.py run`

---

**Last Updated**: September 2025  
**Version**: 1.0
