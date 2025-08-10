from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from core.models import Department, Batch, Subject, TimeBlock, Student, Section
from datetime import datetime, time
import json

@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class AttendanceFormAPIView(View):
    """API views for attendance form data"""
    
    def get(self, request, *args, **kwargs):
        action = request.GET.get('action')
        
        if action == 'departments':
            return self.get_departments()
        elif action == 'batches':
            dept_param = request.GET.get('dept_id') or request.GET.get('dept_name')
            return self.get_batches(dept_param)
        elif action == 'subjects':
            dept_param = request.GET.get('dept_id') or request.GET.get('dept_name')
            batch_year = request.GET.get('batch_year')
            return self.get_subjects(dept_param, batch_year)
        elif action == 'current_time_slot':
            batch_year = request.GET.get('batch_year')
            return self.get_current_time_slot(batch_year)
        elif action == 'students':
            departments = request.GET.get('departments', '').split(',')
            batch_year = request.GET.get('batch_year')
            sections = request.GET.get('sections', '').split(',')
            return self.get_students(departments, batch_year, sections)
        else:
            return JsonResponse({'error': 'Invalid action'}, status=400)
    
    def post(self, request, *args, **kwargs):
        """Handle attendance form submission"""
        try:
            data = json.loads(request.body)
            
            # Extract form data
            user = request.user
            dept_name = data.get('dept_name')
            batch_year = data.get('batch_year')
            section = data.get('section', 'A')  # Default section
            subject_code = data.get('subject')
            time_slot = data.get('time_slot')
            
            # Create response data
            response_data = {
                'user': user.get_full_name() or user.username,
                'dept': dept_name,
                'section': section,
                'batch': batch_year,
                'time_slot': time_slot,
                'subject': subject_code,
                'message': 'Attendance form data received successfully!'
            }
            
            return JsonResponse(response_data)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    def get_departments(self):
        """Get all departments"""
        try:
            departments = list(Department.objects.values('dept_id', 'dept_name').order_by('dept_name'))
            return JsonResponse({'departments': departments})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def get_batches(self, dept_param):
        """Get batches for a department (accepts dept_id or dept_name)"""
        try:
            if not dept_param:
                return JsonResponse({'error': 'Department parameter is required'}, status=400)
            
            # Try to convert to int (dept_id), otherwise treat as dept_name
            try:
                dept_id = int(dept_param)
                batches = Batch.objects.filter(dept__dept_id=dept_id).order_by('batch_year')
            except ValueError:
                # It's a dept_name
                batches = Batch.objects.filter(dept__dept_name=dept_param).order_by('batch_year')
            
            batch_list = []
            for batch in batches:
                batch_list.append({
                    'batch_year': batch.batch_year,
                    'display_year': batch.display_year,
                    'current_year': batch.current_year
                })
            
            return JsonResponse({'batches': batch_list})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def get_subjects(self, dept_param, batch_year):
        """Get subjects for a department and batch"""
        try:
            if not dept_param or not batch_year:
                return JsonResponse({'error': 'Department parameter and batch year are required'}, status=400)
            
            # Get the current year for this batch
            try:
                # Try to convert to int (dept_id), otherwise treat as dept_name
                try:
                    dept_id = int(dept_param)
                    batch = Batch.objects.get(dept__dept_id=dept_id, batch_year=int(batch_year))
                except ValueError:
                    # It's a dept_name
                    batch = Batch.objects.get(dept__dept_name=dept_param, batch_year=int(batch_year))
                
                current_year = batch.current_year
            except Batch.DoesNotExist:
                return JsonResponse({'error': 'Batch not found'}, status=404)
            
            # Get subjects for this department and year
            try:
                dept_id = int(dept_param)
                subjects = Subject.objects.filter(departments__dept_id=dept_id, year=current_year)
            except ValueError:
                subjects = Subject.objects.filter(departments__dept_name=dept_param, year=current_year)
            
            subjects_list = subjects.values('subject_code', 'subject_name').order_by('subject_name')
            
            return JsonResponse({'subjects': list(subjects_list)})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def get_current_time_slot(self, batch_year):
        """Get current time slot based on batch year and current time"""
        try:
            if not batch_year:
                return JsonResponse({'error': 'Batch year is required'}, status=400)
            
            # Verify that at least one batch exists for this year
            batch_exists = Batch.objects.filter(batch_year=int(batch_year)).exists()
            if not batch_exists:
                return JsonResponse({'error': 'Batch not found'}, status=404)
            
            current_time = datetime.now().time()
            
            # Get time blocks for this specific batch year, or fall back to general time blocks (batch_year=0)
            time_blocks = TimeBlock.objects.filter(
                batch_year__in=[int(batch_year), 0]
            ).order_by('-batch_year', 'block_number')  # Prefer specific batch over general
            
            if not time_blocks.exists():
                return JsonResponse({
                    'current_time_slot': None,
                    'current_time': current_time.strftime('%H:%M'),
                    'message': f'No time blocks configured for batch {batch_year}'
                })
            
            current_block = None
            next_block = None
            
            for block in time_blocks:
                if block.start_time <= current_time <= block.end_time:
                    current_block = block
                    break
                elif current_time < block.start_time and next_block is None:
                    next_block = block
            
            if current_block:
                return JsonResponse({
                    'current_time_slot': {
                        'block_number': current_block.block_number,
                        'start_time': current_block.start_time.strftime('%H:%M'),
                        'end_time': current_block.end_time.strftime('%H:%M'),
                        'status': 'active'
                    },
                    'current_time': current_time.strftime('%H:%M'),
                    'batch_year': int(batch_year)
                })
            elif next_block:
                return JsonResponse({
                    'current_time_slot': {
                        'block_number': next_block.block_number,
                        'start_time': next_block.start_time.strftime('%H:%M'),
                        'end_time': next_block.end_time.strftime('%H:%M'),
                        'status': 'upcoming'
                    },
                    'current_time': current_time.strftime('%H:%M'),
                    'batch_year': int(batch_year)
                })
            else:
                return JsonResponse({
                    'current_time_slot': None,
                    'current_time': current_time.strftime('%H:%M'),
                    'message': f'No active or upcoming classes for batch {batch_year}',
                    'batch_year': int(batch_year)
                })
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def get_students(self, departments, batch_year, sections):
        """Get students for specified departments, batch year, and sections"""
        try:
            if not departments or not batch_year:
                return JsonResponse({'error': 'Departments and batch year are required'}, status=400)
            
            # Remove empty strings from departments and sections
            departments = [dept for dept in departments if dept.strip()]
            sections = [section for section in sections if section.strip()]
            
            if not departments:
                return JsonResponse({'error': 'At least one department is required'}, status=400)
            
            # Get students from the specified departments, batch year, and sections
            students_query = Student.objects.select_related('section', 'section__batch', 'section__batch__dept')
            
            # Filter by departments
            students_query = students_query.filter(
                section__batch__dept__dept_name__in=departments
            )
            
            # Filter by batch year
            students_query = students_query.filter(
                section__batch__batch_year=int(batch_year)
            )
            
            # Filter by sections if specified
            if sections and sections != ['A']:  # Default to all sections if only 'A' is specified
                # Handle both "A" format and "DeptName-A" format
                section_names = []
                for section in sections:
                    if '-' in section:
                        section_names.append(section.split('-')[-1])
                    else:
                        section_names.append(section)
                
                students_query = students_query.filter(
                    section__section_name__in=section_names
                )
            
            students = students_query.order_by('section__section_name', 'register_number')
            
            students_list = []
            for student in students:
                students_list.append({
                    'id': student.student_id,
                    'student_id': student.student_id,
                    'name': student.name,
                    'register_number': student.register_number,
                    'department': student.section.batch.dept.dept_name,
                    'section': student.section.section_name,
                    'batch_year': student.section.batch.batch_year,
                    'display_year': student.section.batch.display_year
                })
            
            return JsonResponse({
                'students': students_list,
                'count': len(students_list)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class TimeBlocksAPIView(View):
    """API for getting all time blocks"""
    
    def get(self, request, *args, **kwargs):
        """Get all time blocks"""
        try:
            time_blocks = TimeBlock.objects.all().order_by('batch_year', 'block_number')
            
            blocks_data = []
            for block in time_blocks:
                blocks_data.append({
                    'batch_year': block.batch_year,
                    'block_number': block.block_number,
                    'start_time': block.start_time.strftime('%H:%M'),
                    'end_time': block.end_time.strftime('%H:%M')
                })
            
            return JsonResponse({'time_blocks': blocks_data})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
