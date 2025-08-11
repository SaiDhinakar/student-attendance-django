#!/usr/bin/env python
"""
Scri    print("=== EXIS    print("\n=== AVAILABLE SECTIONS (First 10) ===")
    sections = Section.objects.all()[:10]
    for section in sections:
        print(f"Section: {section.section_name} - {section.batch.dept.dept_name} (Batch Year: {section.batch.batch_year})") ADVISOR PROFILES ===")
    for advisor in Advisor.objects.all():
        print(f"Advisor: {advisor.user.username} - {advisor.employee_id}")
        print(f"  Departments: {[d.dept_name for d in advisor.departments.all()]}")
        print(f"  Batches: {[f'{b.dept.dept_name}-{b.batch_year}' for b in advisor.batches.all()]}")
        print(f"  Sections: {[s.section_name for s in advisor.sections.all()]}")
        print()reate advisor profiles for existing users
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
from advisor_dashboard.models import Advisor
from core.models import Department, Batch, Section

def check_and_create_advisor_profiles():
    """Check existing users and create advisor profiles"""
    
    print("=== EXISTING USERS ===")
    for user in User.objects.all():
        print(f"User: {user.username} ({user.first_name} {user.last_name})")
        print(f"  Email: {user.email}")
        print(f"  Groups: {[g.name for g in user.groups.all()]}")
        print(f"  Has advisor profile: {hasattr(user, 'advisor_profile')}")
        print()

    print("=== EXISTING ADVISOR PROFILES ===")
    for advisor in Advisor.objects.all():
        print(f"Advisor: {advisor.user.username} - {advisor.employee_id}")
        print(f"  Departments: {[d.dept_name for d in advisor.departments.all()]}")
        print(f"  Batches: {[f'{b.dept.dept_name}-{b.batch_year}' for b in advisor.batches.all()]}")
        print(f"  Sections: {[s.section_name for s in advisor.sections.all()]}")
        print()

    print("=== AVAILABLE DEPARTMENTS ===")
    departments = Department.objects.all()
    for dept in departments:
        print(f"Dept: {dept.dept_name} (ID: {dept.dept_id})")
    
    print("\n=== AVAILABLE SECTIONS (First 10) ===")
    sections = Section.objects.all()[:10]
    for section in sections:
        print(f"Section: {section.section_name} - {section.batch.dept.dept_name} (Batch: {section.batch.batch_year})")

    print("\n=== CREATING ADVISOR PROFILES ===")
    
    # Find users in Advisors group who don't have advisor profiles
    advisor_users = User.objects.filter(groups__name='Advisors')
    
    for user in advisor_users:
        if not hasattr(user, 'advisor_profile'):
            try:
                # Create advisor profile
                advisor = Advisor.objects.create(
                    user=user,
                    employee_id=f"ADV{user.id:03d}",
                    phone=f"+123456789{user.id}",
                    office_location=f"Room {100 + user.id}, Admin Block",
                    can_take_attendance=True,
                    can_view_all_attendance=True,
                    can_edit_attendance=True,
                    can_generate_reports=True,
                )
                print(f"✅ Created advisor profile for {user.username} - {advisor.employee_id}")
                
                # Assign some departments and sections
                if departments.exists():
                    # Assign first department
                    advisor.departments.add(departments.first())
                    print(f"   📍 Assigned department: {departments.first().dept_name}")
                
                if sections.exists():
                    # Assign first 3 sections
                    advisor.sections.set(sections[:3])
                    section_names = [s.section_name for s in sections[:3]]
                    print(f"   📚 Assigned sections: {', '.join(section_names)}")
                
                advisor.save()
                
            except Exception as e:
                print(f"❌ Error creating advisor profile for {user.username}: {e}")
        else:
            print(f"ℹ️  User {user.username} already has advisor profile")

    print("\n=== FINAL CHECK ===")
    print(f"Total Users: {User.objects.count()}")
    print(f"Total Advisor Profiles: {Advisor.objects.count()}")
    print(f"Users in Advisors group: {User.objects.filter(groups__name='Advisors').count()}")

if __name__ == '__main__':
    check_and_create_advisor_profiles()
