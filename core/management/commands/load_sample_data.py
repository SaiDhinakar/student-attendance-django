from django.core.management.base import BaseCommand
from core.models import Department, Batch, Subject, TimeBlock, Section, Student
from datetime import time


class Command(BaseCommand):
    help = 'Load sample data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Loading sample data...')
        
        # Create sample departments
        departments_data = [
            {'dept_id': 1, 'dept_name': 'Computer Science'},
            {'dept_id': 2, 'dept_name': 'Information Technology'},
            {'dept_id': 3, 'dept_name': 'Electronics'},
            {'dept_id': 4, 'dept_name': 'Mechanical'},
            {'dept_id': 5, 'dept_name': 'Civil'},
        ]
        
        for dept_data in departments_data:
            dept, created = Department.objects.get_or_create(
                dept_id=dept_data['dept_id'],
                defaults={'dept_name': dept_data['dept_name']}
            )
            if created:
                self.stdout.write(f'Created department: {dept.dept_name}')
        
        # Create sample batches
        current_year = 2025
        for dept in Department.objects.all():
            for graduation_year in [2025, 2026, 2027, 2028]:
                batch, created = Batch.objects.get_or_create(
                    dept=dept,
                    batch_year=graduation_year
                )
                if created:
                    self.stdout.write(f'Created batch: {batch}')
        
        # Create sample time blocks for all batches (use 0 for universal time blocks)
        time_blocks_data = [
            # Universal time blocks (batch_year=0 means applies to all batches)
            {'batch_year': 0, 'block_number': 1, 'start_time': time(9, 0), 'end_time': time(9, 50)},
            {'batch_year': 0, 'block_number': 2, 'start_time': time(10, 0), 'end_time': time(10, 50)},
            {'batch_year': 0, 'block_number': 3, 'start_time': time(11, 0), 'end_time': time(11, 50)},
            {'batch_year': 0, 'block_number': 4, 'start_time': time(12, 0), 'end_time': time(12, 50)},
            {'batch_year': 0, 'block_number': 5, 'start_time': time(14, 0), 'end_time': time(14, 50)},
            {'batch_year': 0, 'block_number': 6, 'start_time': time(15, 0), 'end_time': time(15, 50)},
            {'batch_year': 0, 'block_number': 7, 'start_time': time(16, 0), 'end_time': time(16, 50)},
            
            # Optional: Specific time blocks for certain batches (if needed)
            # {'batch_year': 2027, 'block_number': 1, 'start_time': time(8, 30), 'end_time': time(9, 20)},
            # {'batch_year': 2027, 'block_number': 2, 'start_time': time(9, 30), 'end_time': time(10, 20)},
        ]
        
        for block_data in time_blocks_data:
            time_block, created = TimeBlock.objects.get_or_create(
                batch_year=block_data['batch_year'],
                block_number=block_data['block_number'],
                defaults={
                    'start_time': block_data['start_time'],
                    'end_time': block_data['end_time']
                }
            )
            if created:
                self.stdout.write(f'Created time block: {time_block}')
        
        # Create sample subjects
        subjects_data = [
            # Year 1 subjects
            {'subject_code': 'CS101', 'subject_name': 'Programming Fundamentals', 'year': 1},
            {'subject_code': 'MA101', 'subject_name': 'Engineering Mathematics I', 'year': 1},
            {'subject_code': 'PH101', 'subject_name': 'Engineering Physics', 'year': 1},
            {'subject_code': 'CH101', 'subject_name': 'Engineering Chemistry', 'year': 1},
            
            # Year 2 subjects
            {'subject_code': 'CS201', 'subject_name': 'Data Structures', 'year': 2},
            {'subject_code': 'CS202', 'subject_name': 'Object Oriented Programming', 'year': 2},
            {'subject_code': 'MA201', 'subject_name': 'Engineering Mathematics II', 'year': 2},
            {'subject_code': 'CS203', 'subject_name': 'Digital Logic Design', 'year': 2},
            
            # Year 3 subjects
            {'subject_code': 'CS301', 'subject_name': 'Database Management Systems', 'year': 3},
            {'subject_code': 'CS302', 'subject_name': 'Computer Networks', 'year': 3},
            {'subject_code': 'CS303', 'subject_name': 'Operating Systems', 'year': 3},
            {'subject_code': 'CS304', 'subject_name': 'Software Engineering', 'year': 3},
            
            # Year 4 subjects
            {'subject_code': 'CS401', 'subject_name': 'Machine Learning', 'year': 4},
            {'subject_code': 'CS402', 'subject_name': 'Distributed Systems', 'year': 4},
            {'subject_code': 'CS403', 'subject_name': 'Capstone Project', 'year': 4},
        ]
        
        for subject_data in subjects_data:
            subject, created = Subject.objects.get_or_create(
                subject_code=subject_data['subject_code'],
                defaults={
                    'subject_name': subject_data['subject_name'],
                    'year': subject_data['year']
                }
            )
            if created:
                # Add all departments to each subject
                subject.departments.set(Department.objects.all())
                self.stdout.write(f'Created subject: {subject}')
        
        # Create sample sections
        for batch in Batch.objects.all():
            for section_name in ['A', 'B', 'C']:
                section, created = Section.objects.get_or_create(
                    batch=batch,
                    section_name=section_name
                )
                if created:
                    self.stdout.write(f'Created section: {section}')
        
        # Create sample students
        for section in Section.objects.all():
            for i in range(1, 6):  # 5 students per section
                register_number = f"{section.batch.batch_year}{section.batch.dept.dept_name[:2].upper()}{section.section_name}{i:03d}"
                student, created = Student.objects.get_or_create(
                    register_number=register_number,
                    defaults={
                        'name': f'Student {register_number}',
                        'section': section
                    }
                )
                if created:
                    self.stdout.write(f'Created student: {student}')
        
        self.stdout.write(self.style.SUCCESS('Successfully loaded sample data'))
