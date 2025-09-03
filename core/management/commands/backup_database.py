"""
MySQL Database Backup Management Command
Copies data from main attendance database to backup database
"""
import os
import logging
import mysql.connector
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connections

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Backup attendance database by copying data to backup database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force backup even if backup database doesn\'t exist (will create it)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )

    def handle(self, *args, **options):
        self.verbose = options.get('verbose', False)
        self.force = options.get('force', False)
        
        start_time = datetime.now()
        self.stdout.write(f"🚀 Starting database backup process at {start_time}")
        
        try:
            # Get database configuration
            db_config = self.get_database_config()
            
            # Create backup database if it doesn't exist
            if self.force or self.check_backup_database_exists(db_config):
                self.create_backup_database_if_needed(db_config)
                
                # Perform the backup
                self.backup_database(db_config)
                
                end_time = datetime.now()
                duration = end_time - start_time
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Database backup completed successfully in {duration}"
                    )
                )
                logger.info(f"Backup completed in {duration}")
                
            else:
                raise CommandError("Backup database does not exist. Use --force to create it.")
                
        except Exception as e:
            logger.error(f"Backup failed: {str(e)}")
            raise CommandError(f"Backup failed: {str(e)}")

    def get_database_config(self):
        """Get database configuration from Django settings"""
        db_settings = settings.DATABASES['default']
        
        config = {
            'host': db_settings.get('HOST', 'localhost'),
            'port': int(db_settings.get('PORT', 3306)),
            'user': db_settings.get('USER'),
            'password': db_settings.get('PASSWORD'),
            'main_database': db_settings.get('NAME'),
            'backup_database': os.getenv('BACKUP_DATABASE_NAME', f"{db_settings.get('NAME')}_backup")
        }
        
        if self.verbose:
            self.stdout.write(f"📋 Database config: {config['host']}:{config['port']}")
            self.stdout.write(f"📋 Main DB: {config['main_database']}")
            self.stdout.write(f"📋 Backup DB: {config['backup_database']}")
        
        return config

    def check_backup_database_exists(self, config):
        """Check if backup database exists"""
        try:
            connection = mysql.connector.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password']
            )
            cursor = connection.cursor()
            
            cursor.execute("SHOW DATABASES")
            databases = [db[0] for db in cursor.fetchall()]
            
            exists = config['backup_database'] in databases
            
            cursor.close()
            connection.close()
            
            if self.verbose:
                self.stdout.write(f"🔍 Backup database exists: {exists}")
            
            return exists
            
        except mysql.connector.Error as e:
            logger.error(f"Error checking backup database: {e}")
            return False

    def create_backup_database_if_needed(self, config):
        """Create backup database if it doesn't exist"""
        try:
            connection = mysql.connector.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password']
            )
            cursor = connection.cursor()
            
            # Create backup database
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{config['backup_database']}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            
            if self.verbose:
                self.stdout.write(f"🗃️ Created backup database: {config['backup_database']}")
            
            cursor.close()
            connection.close()
            
        except mysql.connector.Error as e:
            raise CommandError(f"Error creating backup database: {e}")

    def get_tables_to_backup(self, config):
        """Get list of tables from main database"""
        try:
            connection = mysql.connector.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['main_database']
            )
            cursor = connection.cursor()
            
            cursor.execute("SHOW TABLES")
            tables = [table[0] for table in cursor.fetchall()]
            
            cursor.close()
            connection.close()
            
            if self.verbose:
                self.stdout.write(f"📊 Found {len(tables)} tables to backup")
            
            return tables
            
        except mysql.connector.Error as e:
            raise CommandError(f"Error getting tables list: {e}")

    def copy_table_structure(self, config, table_name):
        """Copy table structure from main to backup database"""
        try:
            connection = mysql.connector.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password']
            )
            cursor = connection.cursor()
            
            # Disable foreign key checks temporarily
            cursor.execute(f"USE `{config['backup_database']}`")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # Get CREATE TABLE statement from main database
            cursor.execute(f"SHOW CREATE TABLE `{config['main_database']}`.`{table_name}`")
            create_table_sql = cursor.fetchone()[1]
            
            # Drop table if exists and create new one
            cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
            cursor.execute(create_table_sql)
            
            # Re-enable foreign key checks
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            cursor.close()
            connection.close()
            
            if self.verbose:
                self.stdout.write(f"🏗️ Copied structure for table: {table_name}")
                
        except mysql.connector.Error as e:
            raise CommandError(f"Error copying table structure for {table_name}: {e}")

    def copy_table_data(self, config, table_name):
        """Copy data from main database table to backup database table"""
        try:
            connection = mysql.connector.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password']
            )
            cursor = connection.cursor()
            
            # Disable foreign key checks for data insertion
            cursor.execute(f"USE `{config['backup_database']}`")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # Get row count for progress tracking
            cursor.execute(f"SELECT COUNT(*) FROM `{config['main_database']}`.`{table_name}`")
            row_count = cursor.fetchone()[0]
            
            if row_count == 0:
                if self.verbose:
                    self.stdout.write(f"📝 Table {table_name}: 0 rows (empty)")
                # Re-enable foreign key checks
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                cursor.close()
                connection.close()
                return
            
            # Copy data in batches to handle large tables
            batch_size = int(os.getenv('BACKUP_BATCH_SIZE', 1000))
            
            # Clear existing data in backup table
            cursor.execute(f"DELETE FROM `{config['backup_database']}`.`{table_name}`")
            
            # Copy data in batches
            offset = 0
            while offset < row_count:
                # Get batch of data from main database
                cursor.execute(f"""
                    SELECT * FROM `{config['main_database']}`.`{table_name}` 
                    LIMIT {batch_size} OFFSET {offset}
                """)
                
                batch_data = cursor.fetchall()
                if not batch_data:
                    break
                
                # Get column names for INSERT statement
                cursor.execute(f"DESCRIBE `{config['main_database']}`.`{table_name}`")
                columns = [col[0] for col in cursor.fetchall()]
                
                # Create INSERT statement
                placeholders = ', '.join(['%s'] * len(columns))
                columns_str = ', '.join([f"`{col}`" for col in columns])
                insert_sql = f"""
                    INSERT INTO `{config['backup_database']}`.`{table_name}` 
                    ({columns_str}) VALUES ({placeholders})
                """
                
                # Insert batch data
                cursor.executemany(insert_sql, batch_data)
                connection.commit()
                
                offset += batch_size
                
                if self.verbose:
                    progress = min(offset, row_count)
                    self.stdout.write(f"📝 Table {table_name}: {progress}/{row_count} rows copied")
            
            # Re-enable foreign key checks
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            cursor.close()
            connection.close()
            
            self.stdout.write(f"✅ Copied {row_count} rows for table: {table_name}")
            
        except mysql.connector.Error as e:
            raise CommandError(f"Error copying data for table {table_name}: {e}")

    def backup_database(self, config):
        """Perform the complete backup process"""
        self.stdout.write("🔄 Starting database backup process...")
        
        # Get list of tables to backup
        tables = self.get_tables_to_backup(config)
        
        if not tables:
            self.stdout.write("⚠️ No tables found to backup")
            return
        
        # Process each table
        for i, table in enumerate(tables, 1):
            self.stdout.write(f"🔄 Processing table {i}/{len(tables)}: {table}")
            
            # Copy table structure
            self.copy_table_structure(config, table)
            
            # Copy table data
            self.copy_table_data(config, table)
        
        # Record backup timestamp
        self.record_backup_timestamp(config)
        
        self.stdout.write(f"✅ Successfully backed up {len(tables)} tables")

    def record_backup_timestamp(self, config):
        """Record when the backup was performed"""
        try:
            connection = mysql.connector.connect(
                host=config['host'],
                port=config['port'],
                user=config['user'],
                password=config['password'],
                database=config['backup_database']
            )
            cursor = connection.cursor()
            
            # Create backup log table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backup_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    backup_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    backup_type VARCHAR(50) DEFAULT 'daily_backup',
                    notes TEXT
                )
            """)
            
            # Insert backup record
            cursor.execute("""
                INSERT INTO backup_log (backup_type, notes) 
                VALUES ('daily_backup', 'Automated daily backup completed successfully')
            """)
            
            connection.commit()
            cursor.close()
            connection.close()
            
            if self.verbose:
                self.stdout.write("📝 Recorded backup timestamp")
                
        except mysql.connector.Error as e:
            logger.warning(f"Could not record backup timestamp: {e}")
