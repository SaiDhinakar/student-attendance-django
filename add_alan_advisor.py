#!/usr/bin/env python
"""
Simple script to add advisor Alan for Computer Science department batch 2027
Run this from the Django project root directory
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StudentAttendance.settings')
django.setup()

from django.contrib.auth.models import User, Group
from django.db import transaction
from core.models import Department, Batch
from advisor_dashboard.models import Advisor


def add_alan_advisor():
    """Add advisor Alan for Computer Science department batch 2027"""
    try:
        with transaction.atomic():
            print("🚀 Adding advisor Alan...")
            
            # Create or get the Advisors group
            advisors_group, created = Group.objects.get_or_create(name='Advisors')
            if created:
                print("✅ Created Advisors group")

            # Create or get user Alan
            user, user_created = User.objects.get_or_create(
                username='alan',
                defaults={
                    'first_name': 'Alan',
                    'last_name': 'Advisor',
                    'email': 'alan@university.edu',
                    'is_active': True,
                }
            )
            
            if user_created:
                user.set_password('password123')
                user.save()
                print(f"✅ Created user: {user.username}")
            else:
                print(f"⚠️  User {user.username} already exists")

            # Add user to Advisors group
            user.groups.add(advisors_group)
            
            # Get or create Computer Science department
            cs_dept, dept_created = Department.objects.get_or_create(
                dept_name='Computer Science',
                defaults={'dept_id': 1}
            )
            
            if dept_created:
                print(f"✅ Created department: {cs_dept.dept_name}")
            else:
                print(f"⚠️  Department {cs_dept.dept_name} already exists")

            # Get or create batch 2027 for Computer Science
            batch_2027, batch_created = Batch.objects.get_or_create(
                dept=cs_dept,
                batch_year=2027,
            )
            
            if batch_created:
                print(f"✅ Created batch: {batch_2027}")
            else:
                print(f"⚠️  Batch {batch_2027} already exists")

            # Create or get advisor profile
            advisor, advisor_created = Advisor.objects.get_or_create(
                user=user,
                defaults={
                    'employee_id': 'ADV001',
                    'phone': '+1234567890',
                    'office_location': 'CS Building, Room 201',
                    'can_take_attendance': True,
                    'can_view_all_attendance': True,
                    'can_edit_attendance': True,
                    'can_generate_reports': True,
                }
            )

            if advisor_created:
                print(f"✅ Created advisor profile for: {user.get_full_name()}")
            else:
                print(f"⚠️  Advisor profile for {user.get_full_name()} already exists")

            # Assign department and batch to advisor
            advisor.departments.add(cs_dept)
            advisor.batches.add(batch_2027)
            
            print("\n🎉 Successfully configured advisor Alan!")
            print(f"   📧 Username: {user.username}")
            print(f"   🔑 Password: password123")
            print(f"   🆔 Employee ID: {advisor.employee_id}")
            print(f"   🏫 Assigned to: {cs_dept.dept_name} - Batch {batch_2027.display_year}")
            print(f"   🏢 Office: {advisor.office_location}")
            print("\n💡 Alan can now login and access only Computer Science students from batch 2027!")

    except Exception as e:
        print(f"❌ Error creating advisor: {str(e)}")
        raise e


if __name__ == '__main__':
    add_alan_advisor()
