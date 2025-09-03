#!/usr/bin/env python3
"""
Database Backup Manager and Monitor
Handles scheduled backups and monitoring of backup processes
"""

import os
import sys
import subprocess
import logging
import time
import signal
from datetime import datetime, timedelta
from pathlib import Path

# Add Django project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StudentAttendance.settings')

try:
    import django
    django.setup()
except ImportError:
    print("❌ Error: Could not import Django. Make sure it's installed and DJANGO_SETTINGS_MODULE is set.")
    sys.exit(1)

from django.conf import settings
from dotenv import load_dotenv

# Load backup configuration
backup_config_file = project_root / 'backup_config.env'
if backup_config_file.exists():
    load_dotenv(backup_config_file)

# Set up logging
log_file = os.getenv('BACKUP_LOG_FILE', str(project_root / 'logs' / 'backup.log'))
log_level = getattr(logging, os.getenv('BACKUP_LOG_LEVEL', 'INFO'))

# Ensure log directory exists
Path(log_file).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger('backup_manager')

class BackupManager:
    def __init__(self):
        self.project_root = project_root
        self.python_path = sys.executable
        self.manage_py = self.project_root / 'manage.py'
        self.backup_schedule = os.getenv('BACKUP_SCHEDULE', '0 2 * * *')
        self.running = False
        
        # Handle signals for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    def run_backup(self):
        """Execute the backup command"""
        logger.info("🚀 Starting database backup...")
        
        try:
            # Determine the correct Python executable to use
            python_executable = self.get_python_executable()
            
            # Build command
            cmd = [
                python_executable,
                str(self.manage_py),
                'backup_database',
                '--verbose'
            ]
            
            # Execute backup command
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=int(os.getenv('BACKUP_CONNECTION_TIMEOUT', 1800))  # 30 minutes default
            )
            
            if result.returncode == 0:
                logger.info("✅ Backup completed successfully")
                logger.info(f"Backup output: {result.stdout}")
                return True
            else:
                logger.error(f"❌ Backup failed with exit code {result.returncode}")
                logger.error(f"Error output: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Backup timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Backup failed with exception: {e}")
            return False

    def get_python_executable(self):
        """Get the correct Python executable path"""
        # Check if we have a virtual environment
        venv_python = self.project_root / '.venv' / 'bin' / 'python'
        if venv_python.exists():
            return str(venv_python)
        
        # Use current Python executable
        return sys.executable

    def get_next_backup_time(self):
        """Calculate next backup time based on cron schedule"""
        # For simplicity, we'll parse basic daily schedule
        # Format: "0 2 * * *" means daily at 2:00 AM
        schedule_parts = self.backup_schedule.split()
        
        if len(schedule_parts) >= 2:
            try:
                minute = int(schedule_parts[0])
                hour = int(schedule_parts[1])
                
                now = datetime.now()
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # If the time has already passed today, schedule for tomorrow
                if next_run <= now:
                    next_run += timedelta(days=1)
                
                return next_run
            except ValueError:
                logger.warning(f"Could not parse backup schedule: {self.backup_schedule}")
        
        # Default: run in 24 hours
        return datetime.now() + timedelta(days=1)

    def cleanup_old_backups(self):
        """Clean up old backup logs if retention is set"""
        retention_days = int(os.getenv('BACKUP_RETENTION_DAYS', 0))
        
        if retention_days > 0:
            try:
                from django.db import connection
                
                cutoff_date = datetime.now() - timedelta(days=retention_days)
                
                with connection.cursor() as cursor:
                    # Check if backup database exists and has backup_log table
                    backup_db = os.getenv('BACKUP_DATABASE_NAME', 'attendance_backup')
                    
                    cursor.execute(f"""
                        DELETE FROM `{backup_db}`.backup_log 
                        WHERE backup_timestamp < %s
                    """, [cutoff_date])
                    
                    deleted_count = cursor.rowcount
                    if deleted_count > 0:
                        logger.info(f"🧹 Cleaned up {deleted_count} old backup log entries")
                        
            except Exception as e:
                logger.warning(f"Could not cleanup old backups: {e}")

    def check_backup_health(self):
        """Check the health of the backup system"""
        logger.info("🔍 Performing backup system health check...")
        
        try:
            # Test database connectivity
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            logger.info("✅ Main database connection: OK")
            
            # Check backup database
            backup_db = os.getenv('BACKUP_DATABASE_NAME', 'attendance_backup')
            with connection.cursor() as cursor:
                cursor.execute(f"SHOW DATABASES LIKE '{backup_db}'")
                if cursor.fetchone():
                    logger.info("✅ Backup database exists: OK")
                else:
                    logger.warning("⚠️ Backup database does not exist - will be created on first backup")
            
            # Check disk space (basic check)
            disk_usage = os.statvfs(str(self.project_root))
            free_space_gb = (disk_usage.f_bavail * disk_usage.f_frsize) / (1024**3)
            
            if free_space_gb < 1.0:  # Less than 1GB free
                logger.warning(f"⚠️ Low disk space: {free_space_gb:.2f}GB free")
            else:
                logger.info(f"✅ Disk space: {free_space_gb:.2f}GB free")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False

    def run_scheduled_backup(self):
        """Run backup service in scheduled mode"""
        logger.info("🕐 Starting scheduled backup service...")
        logger.info(f"📅 Backup schedule: {self.backup_schedule}")
        
        self.running = True
        
        # Initial health check
        if not self.check_backup_health():
            logger.error("❌ Initial health check failed, exiting...")
            return False
        
        while self.running:
            try:
                next_backup = self.get_next_backup_time()
                logger.info(f"⏰ Next backup scheduled for: {next_backup}")
                
                # Wait until next backup time
                while datetime.now() < next_backup and self.running:
                    time.sleep(60)  # Check every minute
                
                if not self.running:
                    break
                
                logger.info("🔔 Backup time reached, starting backup...")
                
                # Run the backup
                success = self.run_backup()
                
                if success:
                    # Cleanup old backups
                    self.cleanup_old_backups()
                else:
                    logger.error("❌ Backup failed")
                
            except Exception as e:
                logger.error(f"❌ Error in backup scheduler: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
        
        logger.info("👋 Backup scheduler stopped")
        return True

    def run_immediate_backup(self):
        """Run immediate backup"""
        logger.info("🚀 Running immediate backup...")
        
        # Health check first
        if not self.check_backup_health():
            logger.warning("⚠️ Health check failed, but proceeding with backup...")
        
        success = self.run_backup()
        
        if success:
            self.cleanup_old_backups()
            logger.info("✅ Immediate backup completed successfully")
        else:
            logger.error("❌ Immediate backup failed")
        
        return success

def main():
    """Main entry point"""
    backup_manager = BackupManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'run':
            # Run immediate backup
            success = backup_manager.run_immediate_backup()
            sys.exit(0 if success else 1)
            
        elif command == 'schedule':
            # Run scheduled backup service
            success = backup_manager.run_scheduled_backup()
            sys.exit(0 if success else 1)
            
        elif command == 'health':
            # Run health check only
            success = backup_manager.check_backup_health()
            sys.exit(0 if success else 1)
            
        else:
            print("Usage: python backup_manager.py [run|schedule|health]")
            print("  run      - Run immediate backup")
            print("  schedule - Start scheduled backup service") 
            print("  health   - Run health check only")
            sys.exit(1)
    else:
        print("🔄 Starting backup manager...")
        print("Usage: python backup_manager.py [run|schedule|health]")
        print("  run      - Run immediate backup")
        print("  schedule - Start scheduled backup service")
        print("  health   - Run health check only")
        sys.exit(1)

if __name__ == '__main__':
    main()
