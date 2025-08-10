#!/usr/bin/env python
"""
Management command to load demo data for the attendance system
"""
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append('/mnt/sda1/student-attendance-django')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StudentAttendance.settings')
django.setup()

from django.core.management.base import BaseCommand
from core.models import Department, Batch, Subject, TimeBlock
from datetime import time

class Command(BaseCommand):
    help = 'Load demo data for attendance system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Loading demo data...'))
        
        # Create Departments
        departments_data = [
            {'dept_id': 1, 'dept_name': 'AIML'},
            {'dept_id': 2, 'dept_name': 'CSE'},
            {'dept_id': 3, 'dept_name': 'IT'},
            {'dept_id': 4, 'dept_name': 'ECE'},
        ]
        
        for dept_data in departments_data:
            dept, created = Department.objects.get_or_create(
                dept_id=dept_data['dept_id'],
                defaults={'dept_name': dept_data['dept_name']}
            )
            if created:
                self.stdout.write(f'Created department: {dept.dept_name}')
            else:
                self.stdout.write(f'Department already exists: {dept.dept_name}')
        
        # Get AIML department for batches (main department for demo)
        aiml_dept = Department.objects.get(dept_name='AIML')
        
        # Create Batches
        batches_data = [
            {'batch_year': 2027, 'year': 3},  # Currently 3rd year
            {'batch_year': 2028, 'year': 2},  # Currently 2nd year
            {'batch_year': 2029, 'year': 1},  # Currently 1st year
        ]
        
        for batch_data in batches_data:
            batch, created = Batch.objects.get_or_create(
                dept=aiml_dept,
                batch_year=batch_data['batch_year'],
                defaults={'batch_year': batch_data['batch_year']}
            )
            if created:
                self.stdout.write(f'Created batch: {batch}')
            else:
                self.stdout.write(f'Batch already exists: {batch}')
        
        # Create Subjects
        subjects_data = [
            {'subject_code': 'ML101', 'subject_name': 'Machine Learning', 'year': 3, 'departments': ['AIML']},
            {'subject_code': 'DL101', 'subject_name': 'Deep Learning', 'year': 3, 'departments': ['AIML']},
            {'subject_code': 'CV101', 'subject_name': 'Computer Vision', 'year': 3, 'departments': ['AIML']},
            {'subject_code': 'MLO101', 'subject_name': 'MLOps', 'year': 3, 'departments': ['AIML']},
            {'subject_code': 'DS101', 'subject_name': 'Data Structures', 'year': 2, 'departments': ['AIML', 'CSE']},
            {'subject_code': 'ALGO101', 'subject_name': 'Algorithms', 'year': 2, 'departments': ['AIML', 'CSE']},
            {'subject_code': 'PROG101', 'subject_name': 'Programming Fundamentals', 'year': 1, 'departments': ['AIML', 'CSE', 'IT']},
            {'subject_code': 'MATH101', 'subject_name': 'Mathematics', 'year': 1, 'departments': ['AIML', 'CSE', 'IT', 'ECE']},
        ]
        
        for subject_data in subjects_data:
            subject, created = Subject.objects.get_or_create(
                subject_code=subject_data['subject_code'],
                defaults={
                    'subject_name': subject_data['subject_name'],
                    'year': subject_data['year']
                }
            )
            
            # Add departments to the subject
            for dept_name in subject_data['departments']:
                try:
                    department = Department.objects.get(dept_name=dept_name)
                    subject.departments.add(department)
                except Department.DoesNotExist:
                    self.stdout.write(f'Department {dept_name} not found for subject {subject.subject_code}')
            
            if created:
                self.stdout.write(f'Created subject: {subject}')
            else:
                self.stdout.write(f'Subject already exists: {subject}')
        
        # Create Time Blocks
        self.create_time_blocks()
        
        self.stdout.write(self.style.SUCCESS('Demo data loaded successfully!'))
    
    def create_time_blocks(self):
        """Create time blocks for different years"""
        
        # Time blocks for 2027 batch (3rd year) - 1 hour blocks
        time_blocks_2027 = [
            (3, 1, time(8, 30), time(9, 30)),
            (3, 2, time(9, 30), time(10, 30)),
            (3, 3, time(10, 30), time(11, 30)),  # Break: 10:50-11:05
            (3, 4, time(11, 30), time(12, 30)),
            # Lunch: 12:30-1:20
            (3, 5, time(13, 20), time(14, 20)),
            (3, 6, time(14, 20), time(15, 20)),  # Break: 2:50-3:05
            (3, 7, time(15, 20), time(16, 20)),
        ]
        
        # Time blocks for 2028 batch (2nd year) - 45 minute blocks
        time_blocks_2028 = [
            (2, 1, time(8, 30), time(9, 15)),
            (2, 2, time(9, 15), time(10, 0)),
            (2, 3, time(10, 0), time(10, 45)),
            # Break: 10:30-10:50
            (2, 4, time(10, 50), time(11, 35)),
            (2, 5, time(11, 35), time(12, 20)),
            # Lunch: 12:30-1:20
            (2, 6, time(13, 20), time(14, 5)),
            (2, 7, time(14, 5), time(14, 50)),
            # Break: 2:30-2:50
            (2, 8, time(14, 50), time(15, 35)),
            (2, 9, time(15, 35), time(16, 20)),
        ]
        
        # Time blocks for 2029 batch (1st year) - 45 minute blocks
        time_blocks_2029 = [
            (1, 1, time(8, 30), time(9, 15)),
            (1, 2, time(9, 15), time(10, 0)),
            (1, 3, time(10, 0), time(10, 45)),
            # Break: 10:30-10:50
            (1, 4, time(10, 50), time(11, 35)),
            (1, 5, time(11, 35), time(12, 20)),
            # Lunch: 12:30-1:20
            (1, 6, time(13, 20), time(14, 5)),
            (1, 7, time(14, 5), time(14, 50)),
            # Break: 2:30-2:50
            (1, 8, time(14, 50), time(15, 35)),
            (1, 9, time(15, 35), time(16, 20)),
        ]
        
        all_blocks = time_blocks_2027 + time_blocks_2028 + time_blocks_2029
        
        for batch_year, block_number, start_time, end_time in all_blocks:
            time_block, created = TimeBlock.objects.get_or_create(
                batch_year=batch_year,
                block_number=block_number,
                defaults={
                    'start_time': start_time,
                    'end_time': end_time
                }
            )
            if created:
                self.stdout.write(f'Created time block: {time_block}')

if __name__ == '__main__':
    cmd = Command()
    cmd.handle()
