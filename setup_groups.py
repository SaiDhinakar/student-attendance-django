#!/usr/bin/env python
"""
Script to create user groups and assign permissions
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

def create_groups_and_permissions():
    """Create user groups and assign permissions"""
    
    # Create Advisors group
    advisors_group, created = Group.objects.get_or_create(name='Advisors')
    if created:
        print("Advisors group created successfully!")
    else:
        print("Advisors group already exists!")
    
    # Create Staffs group
    staffs_group, created = Group.objects.get_or_create(name='Staffs')
    if created:
        print("Staffs group created successfully!")
    else:
        print("Staffs group already exists!")
    
    # You can add specific permissions here if needed
    # For now, we'll handle permissions in views using group membership
    
    print("\nGroups created successfully!")
    print("- Advisors: Can access advisor dashboard and view department attendance")
    print("- Staffs: Can only access attendance marking page")

def create_test_users():
    """Create test users for each group"""
    
    # Create advisor user
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
        # Add to Advisors group
        advisors_group = Group.objects.get(name='Advisors')
        advisor_user.groups.add(advisors_group)
        print(f"Advisor user created: advisor_user / advisor123")
    else:
        print("Advisor user already exists!")
    
    # Create staff user
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
        # Add to Staffs group
        staffs_group = Group.objects.get(name='Staffs')
        staff_user.groups.add(staffs_group)
        print(f"Staff user created: staff_user / staff123")
    else:
        print("Staff user already exists!")

if __name__ == '__main__':
    create_groups_and_permissions()
    print("\n" + "="*50)
    create_test_users()
    print("\n" + "="*50)
    print("Setup complete! You can now test the role-based dashboards.")
