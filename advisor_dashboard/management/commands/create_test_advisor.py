from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.contrib.auth.hashers import make_password
from advisor_dashboard.models import Advisor
from core.models import Department, Batch, Section

class Command(BaseCommand):
    help = 'Create test advisor user and groups'

    def handle(self, *args, **options):
        # Create groups if they don't exist
        advisors_group, created = Group.objects.get_or_create(name='Advisors')
        staffs_group, created = Group.objects.get_or_create(name='Staffs')
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created groups: Advisors, Staffs'))
        else:
            self.stdout.write('Groups already exist')

        # Create a test advisor user
        advisor_username = 'advisor_test'
        advisor_email = 'advisor@test.com'
        advisor_password = 'testpass123'
        
        try:
            # Check if user already exists
            advisor_user = User.objects.get(username=advisor_username)
            self.stdout.write(f'User {advisor_username} already exists')
        except User.DoesNotExist:
            # Create the user
            advisor_user = User.objects.create(
                username=advisor_username,
                email=advisor_email,
                password=make_password(advisor_password),
                first_name='Test',
                last_name='Advisor',
                is_staff=True,
                is_active=True
            )
            self.stdout.write(self.style.SUCCESS(f'Created user: {advisor_username}'))

        # Add user to Advisors group
        advisor_user.groups.add(advisors_group)
        
        # Create advisor profile if it doesn't exist
        try:
            advisor_profile = advisor_user.advisor_profile
            self.stdout.write('Advisor profile already exists')
        except:
            advisor_profile = Advisor.objects.create(
                user=advisor_user,
                employee_id='ADV001',
                phone='1234567890',
                office_location='Room 101'
            )
            self.stdout.write(self.style.SUCCESS('Created advisor profile'))
            
            # Assign to first available department if any exist
            try:
                first_dept = Department.objects.first()
                if first_dept:
                    advisor_profile.departments.add(first_dept)
                    self.stdout.write(f'Assigned advisor to department: {first_dept.dept_name}')
            except:
                pass

        self.stdout.write(
            self.style.SUCCESS(
                f'Setup complete!\n'
                f'Username: {advisor_username}\n'
                f'Password: {advisor_password}\n'
                f'You can now log in as an advisor.'
            )
        )
