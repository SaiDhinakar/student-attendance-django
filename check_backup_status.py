#!/usr/bin/env python3
"""
Simple script to check backup database status
"""
import mysql.connector
import os
from datetime import datetime

def check_backup_status():
    try:
        # Connect to backup database
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='1234',
            database='attendance_backup'
        )
        cursor = conn.cursor()

        print("🔍 Backup Database Status Check")
        print("=" * 40)

        # Check tables
        cursor.execute('SHOW TABLES')
        tables = [table[0] for table in cursor.fetchall()]
        print(f"📊 Total tables in backup: {len(tables)}")

        # Key tables with their counts
        key_tables = ['Students', 'Attendance', 'attendance_predictions', 'backup_log']
        print("\n📋 Key table counts:")
        
        for table in key_tables:
            if table in tables:
                cursor.execute(f'SELECT COUNT(*) FROM `{table}`')
                count = cursor.fetchone()[0]
                print(f"   {table:25}: {count:>6} rows")

        # Last backup info
        print("\n🕐 Backup History:")
        cursor.execute('SELECT * FROM backup_log ORDER BY backup_timestamp DESC LIMIT 3')
        backups = cursor.fetchall()
        
        if backups:
            for backup in backups:
                print(f"   {backup[1]} - {backup[2]} - {backup[3] or 'No notes'}")
        else:
            print("   No backup history found")

        cursor.close()
        conn.close()
        
        print("\n✅ Backup database is operational!")
        return True

    except mysql.connector.Error as e:
        print(f"❌ Error connecting to backup database: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    check_backup_status()
