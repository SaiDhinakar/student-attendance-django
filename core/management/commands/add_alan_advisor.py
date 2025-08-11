"""
Django management command to add advisor Alan for Computer Science department batch 2027
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction
from core.models import Department, Batch
from advisor_dashboard.models import Advisor


class Command(BaseCommand):
    help = 'Add advisor Alan for Computer Science department batch 2027'

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                # Create or get the Advisors group
                advisors_group, created = Group.objects.get_or_create(name='Advisors')
                if created:
                    self.stdout.write(
                        self.style.SUCCESS('Created Advisors group')
                    )

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
                    user.set_password('password123')  # Set a default password
                    user.save()
                    self.stdout.write(
                        self.style.SUCCESS(f'Created user: {user.username}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'User {user.username} already exists')
                    )

                # Add user to Advisors group
                user.groups.add(advisors_group)
                
                # Get or create Computer Science department
                cs_dept, dept_created = Department.objects.get_or_create(
                    dept_name='Computer Science',
                    defaults={'dept_id': 1}  # You might need to adjust this ID
                )
                
                if dept_created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created department: {cs_dept.dept_name}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Department {cs_dept.dept_name} already exists')
                    )

                # Get or create batch 2027 for Computer Science
                batch_2027, batch_created = Batch.objects.get_or_create(
                    dept=cs_dept,
                    batch_year=2027,
                )
                
                if batch_created:
                    self.stdout.write(
                        self.style.SUCCESS(f'Created batch: {batch_2027}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Batch {batch_2027} already exists')
                    )

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
                    self.stdout.write(
                        self.style.SUCCESS(f'Created advisor profile for: {user.get_full_name()}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Advisor profile for {user.get_full_name()} already exists')
                    )

                # Assign department and batch to advisor
                advisor.departments.add(cs_dept)
                advisor.batches.add(batch_2027)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Successfully configured advisor {user.get_full_name()}'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'   - Username: {user.username}'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'   - Password: password123'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'   - Employee ID: {advisor.employee_id}'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'   - Assigned to: {cs_dept.dept_name} - Batch {batch_2027.display_year}'
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'   - Office: {advisor.office_location}'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error creating advisor: {str(e)}')
            )
            raise e
