#!/usr/bin/env python
"""
Create a test advisor user for testing the advisor dashboard
"""
import os
import sys
import django

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StudentAttendance.settings')
django.setup()

from django.contrib.auth.models import User, Group
from django.db import IntegrityError
from advisor_dashboard.models import Advisor
from core.models import Department, Batch, Section

def create_test_advisor():
    """Create a test advisor user with sample data"""
    
    # Create Advisors group if it doesn't exist
    advisors_group, created = Group.objects.get_or_create(name='Advisors')
    if created:
        print("Created 'Advisors' group")
    
    # Create test user
    try:
        user = User.objects.create_user(
            username='advisor1',
            email='advisor1@example.com',
            password='testpass123',
            first_name='John',
            last_name='Advisor'
        )
        user.is_staff = True
        user.save()
        
        # Add user to Advisors group
        user.groups.add(advisors_group)
        
        print(f"Created user: {user.username}")
    except IntegrityError:
        user = User.objects.get(username='advisor1')
        user.is_staff = True
        user.save()
        user.groups.add(advisors_group)
        print(f"User {user.username} already exists, updated permissions")
    
    # Create advisor profile
    advisor, created = Advisor.objects.get_or_create(
        user=user,
        defaults={
            'employee_id': 'ADV001',
            'phone': '+1234567890',
            'office_location': 'Room 101, Admin Block',
            'can_take_attendance': True,
            'can_view_all_attendance': True,
            'can_edit_attendance': True,
            'can_generate_reports': True,
        }
    )
    
    if created:
        print(f"Created advisor profile: {advisor}")
    else:
        print(f"Advisor profile already exists: {advisor}")
    
    # Assign some departments/batches/sections to the advisor if they exist
    departments = Department.objects.all()[:2]  # First 2 departments
    if departments:
        advisor.departments.set(departments)
        print(f"Assigned departments: {[d.dept_name for d in departments]}")
    
    batches = Batch.objects.all()[:3]  # First 3 batches
    if batches:
        advisor.batches.set(batches)
        print(f"Assigned batches: {[b.year for b in batches]}")
    
    sections = Section.objects.all()[:5]  # First 5 sections
    if sections:
        advisor.sections.set(sections)
        print(f"Assigned sections: {[s.section_name for s in sections]}")
    
    print("\n=== Test Advisor Created Successfully ===")
    print(f"Username: advisor1")
    print(f"Password: testpass123")
    print(f"Employee ID: {advisor.employee_id}")
    print(f"Assigned Students: {advisor.get_assigned_students().count()}")
    print(f"Assigned Sections: {advisor.get_assigned_sections().count()}")
    print("========================================")

if __name__ == '__main__':
    create_test_advisor()
