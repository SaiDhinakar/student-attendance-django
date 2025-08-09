#!/usr/bin/env python
"""
Script to create a staff user for testing the attendance dashboard
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append('/mnt/sda1/student-attendance-django')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StudentAttendance.settings')
django.setup()

from django.contrib.auth.models import User

def create_staff_user():
    """Create a staff user for testing"""
    
    # Check if staff user already exists
    if User.objects.filter(username='staff_user').exists():
        print("Staff user already exists!")
        return
    
    # Create staff user
    staff_user = User.objects.create_user(
        username='staff_user',
        email='staff@example.com',
        password='staff123',
        first_name='Staff',
        last_name='Member',
        is_staff=True,
        is_superuser=False  # This makes them a staff user, not an admin
    )
    
    print(f"Staff user created successfully!")
    print(f"Username: staff_user")
    print(f"Password: staff123")
    print(f"This user will be redirected to the attendance dashboard upon login.")

if __name__ == '__main__':
    create_staff_user()
