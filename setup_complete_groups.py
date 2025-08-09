#!/usr/bin/env python
"""
Script to set up user groups and create test users for the attendance system
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append('/mnt/sda1/student-attendance-django')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StudentAttendance.settings')
django.setup()

from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType

def setup_groups():
    """Create user groups and set permissions"""
    
    # Create groups
    advisors_group, created = Group.objects.get_or_create(name='Advisors')
    if created:
        print("Created 'Advisors' group")
    else:
        print("'Advisors' group already exists")
    
    staffs_group, created = Group.objects.get_or_create(name='Staffs')
    if created:
        print("Created 'Staffs' group")
    else:
        print("'Staffs' group already exists")
    
    return advisors_group, staffs_group

def create_test_users():
    """Create test users for different roles"""
    
    advisors_group, staffs_group = setup_groups()
    
    # Create Advisor user
    if not User.objects.filter(username='advisor_user').exists():
        advisor_user = User.objects.create_user(
            username='advisor_user',
            email='advisor@example.com',
            password='advisor123',
            first_name='John',
            last_name='Advisor',
            is_staff=True,
            is_superuser=False
        )
        advisor_user.groups.add(advisors_group)
        print("Created advisor user:")
        print(f"  Username: advisor_user")
        print(f"  Password: advisor123")
        print(f"  Role: Advisor (can mark attendance and view department reports)")
    else:
        print("Advisor user already exists")
    
    # Create Staff user
    if not User.objects.filter(username='staff_user').exists():
        staff_user = User.objects.create_user(
            username='staff_user',
            email='staff@example.com',
            password='staff123',
            first_name='Jane',
            last_name='Staff',
            is_staff=True,
            is_superuser=False
        )
        staff_user.groups.add(staffs_group)
        print("Created staff user:")
        print(f"  Username: staff_user")
        print(f"  Password: staff123")
        print(f"  Role: Staff (can only mark attendance)")
    else:
        print("Staff user already exists")
    
    # Create Superuser if it doesn't exist
    if not User.objects.filter(is_superuser=True).exists():
        superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        print("Created superuser:")
        print(f"  Username: admin")
        print(f"  Password: admin123")
        print(f"  Role: Admin (full access to admin panel)")
    else:
        print("Superuser already exists")

def display_user_roles():
    """Display all users and their roles"""
    print("\n" + "="*50)
    print("USER ROLES SUMMARY")
    print("="*50)
    
    users = User.objects.all()
    for user in users:
        print(f"\nUser: {user.username} ({user.get_full_name() or 'No full name'})")
        print(f"  Email: {user.email}")
        print(f"  Is Staff: {user.is_staff}")
        print(f"  Is Superuser: {user.is_superuser}")
        
        groups = user.groups.all()
        if groups:
            group_names = [group.name for group in groups]
            print(f"  Groups: {', '.join(group_names)}")
        else:
            print("  Groups: None")
        
        # Determine role
        if user.is_superuser:
            role = "Admin (redirects to admin panel)"
        elif user.groups.filter(name='Advisors').exists():
            role = "Advisor (redirects to advisor dashboard)"
        elif user.groups.filter(name='Staffs').exists():
            role = "Staff (redirects to staff attendance marking)"
        elif user.is_staff:
            role = "General Staff (redirects to staff dashboard)"
        else:
            role = "Regular User (no dashboard access)"
        
        print(f"  Role: {role}")

if __name__ == '__main__':
    print("Setting up user groups and test users...")
    setup_groups()
    create_test_users()
    display_user_roles()
    
    print("\n" + "="*50)
    print("SETUP COMPLETE!")
    print("="*50)
    print("\nYou can now test the system with:")
    print("1. Admin user - goes to admin panel")
    print("2. Advisor user - goes to advisor dashboard") 
    print("3. Staff user - goes to attendance marking only")
    print("\nLogin at: http://127.0.0.1:8000/auth/login/")
