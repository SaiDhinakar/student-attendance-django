"""
Django management command to update advisor permissions for Computer Science 2027 Batch B section only
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction
from core.models import Department, Batch, Section, Student
from advisor_dashboard.models import Advisor


class Command(BaseCommand):
    help = 'Update advisor to handle only Computer Science 2027 Batch B section'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            default='alan',
            help='Username of the advisor to update (default: alan)',
        )

    def handle(self, *args, **options):
        username = options['username']
        
        try:
            with transaction.atomic():
                self.stdout.write(f"🔧 Updating advisor {username} permissions...")
                
                # Get the user
                try:
                    user = User.objects.get(username=username)
                    self.stdout.write(f"✅ Found user: {user.get_full_name() or user.username}")
                except User.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"❌ User '{username}' not found"))
                    return

                # Get or create advisor profile
                advisor, created = Advisor.objects.get_or_create(
                    user=user,
                    defaults={
                        'employee_id': f'ADV_{user.id:03d}',
                        'phone': '+1234567890',
                        'office_location': 'CS Building, Room 201',
                        'can_take_attendance': True,
                        'can_view_all_attendance': True,
                        'can_edit_attendance': True,
                        'can_generate_reports': True,
                    }
                )

                if created:
                    self.stdout.write(f"✅ Created advisor profile")
                else:
                    self.stdout.write(f"✅ Using existing advisor profile")

                # Get or create Computer Science department
                cs_dept, dept_created = Department.objects.get_or_create(
                    dept_name='Computer Science',
                    defaults={'dept_id': 1}
                )
                
                if dept_created:
                    self.stdout.write(f"✅ Created department: {cs_dept.dept_name}")

                # Get or create batch 2027 for Computer Science
                batch_2027, batch_created = Batch.objects.get_or_create(
                    dept=cs_dept,
                    batch_year=2027,
                )
                
                if batch_created:
                    self.stdout.write(f"✅ Created batch: {batch_2027}")

                # Get or create section B for the batch
                section_b, section_created = Section.objects.get_or_create(
                    batch=batch_2027,
                    section_name='B',
                    defaults={
                        'section_id': f'CS2027B',
                    }
                )
                
                if section_created:
                    self.stdout.write(f"✅ Created section: {section_b}")

                # Clear all existing assignments for this advisor
                advisor.departments.clear()
                advisor.batches.clear()
                advisor.sections.clear()
                
                self.stdout.write("🧹 Cleared all existing advisor assignments")

                # Assign ONLY the specific section
                advisor.sections.add(section_b)
                
                # Also assign the department and batch for reference (but filtering will be by section)
                advisor.departments.add(cs_dept)
                advisor.batches.add(batch_2027)
                
                self.stdout.write("🎯 Assigned specific section, department, and batch")

                # Create some sample students in section B if they don't exist
                students_created = 0
                for i in range(1, 6):  # Create 5 students
                    student_regno = f"CS2027B{i:03d}"
                    student, student_created = Student.objects.get_or_create(
                        student_regno=student_regno,
                        defaults={
                            'name': f'Student {i} Section B',
                            'department': cs_dept,
                            'batch': batch_2027,
                            'section': section_b,
                        }
                    )
                    if student_created:
                        students_created += 1

                if students_created > 0:
                    self.stdout.write(f"✅ Created {students_created} sample students in section B")

                # Create a student in section A to verify filtering
                section_a, _ = Section.objects.get_or_create(
                    batch=batch_2027,
                    section_name='A',
                    defaults={'section_id': f'CS2027A'}
                )
                
                Student.objects.get_or_create(
                    student_regno="CS2027A001",
                    defaults={
                        'name': 'Student 1 Section A (should NOT be visible to advisor)',
                        'department': cs_dept,
                        'batch': batch_2027,
                        'section': section_a,
                    }
                )

                # Verify the setup
                assigned_students = advisor.get_assigned_students()
                assigned_sections = advisor.get_assigned_sections()
                
                self.stdout.write("\n🎉 ADVISOR SETUP COMPLETE!")
                self.stdout.write(f"👤 Advisor: {user.get_full_name() or user.username} ({user.username})")
                self.stdout.write(f"🆔 Employee ID: {advisor.employee_id}")
                self.stdout.write(f"🏫 Department: {cs_dept.dept_name}")
                self.stdout.write(f"📅 Batch: {batch_2027.display_year}")
                self.stdout.write(f"📝 Section: {section_b.section_name}")
                self.stdout.write(f"👥 Assigned Students: {assigned_students.count()}")
                self.stdout.write(f"📚 Assigned Sections: {assigned_sections.count()}")
                
                self.stdout.write("\n📋 Students visible to this advisor:")
                for student in assigned_students:
                    self.stdout.write(f"  • {student.student_regno}: {student.name} (Section {student.section.section_name})")
                
                self.stdout.write("\n📚 Sections visible to this advisor:")
                for section in assigned_sections:
                    self.stdout.write(f"  • {section.section_name} - {section.batch.dept.dept_name} {section.batch.display_year}")

                self.stdout.write(f"\n💡 Login credentials:")
                self.stdout.write(f"   Username: {user.username}")
                self.stdout.write(f"   Password: password123")
                self.stdout.write(f"\n🔒 This advisor can ONLY see Computer Science 2027 Batch B students!")

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error updating advisor: {str(e)}')
            )
            raise e
