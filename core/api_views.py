from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from core.models import Department, Batch, Subject, TimeBlock
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
            
            # Get the current year for this batch
            try:
                batch = Batch.objects.get(batch_year=int(batch_year))
                current_year = batch.current_year
            except Batch.DoesNotExist:
                return JsonResponse({'error': 'Batch not found'}, status=404)
            
            current_time = datetime.now().time()
            
            # Get time blocks for this year
            time_blocks = TimeBlock.objects.filter(
                batch_year=current_year
            ).order_by('block_number')
            
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
                    'current_time': current_time.strftime('%H:%M')
                })
            elif next_block:
                return JsonResponse({
                    'current_time_slot': {
                        'block_number': next_block.block_number,
                        'start_time': next_block.start_time.strftime('%H:%M'),
                        'end_time': next_block.end_time.strftime('%H:%M'),
                        'status': 'upcoming'
                    },
                    'current_time': current_time.strftime('%H:%M')
                })
            else:
                return JsonResponse({
                    'current_time_slot': None,
                    'current_time': current_time.strftime('%H:%M'),
                    'message': 'No active or upcoming classes'
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

    def get_students(self, departments, batch_year, sections):
        """Get students for selected departments, batch and sections"""
        try:
            if not departments or not batch_year:
                return JsonResponse({'error': 'Departments and batch year are required'}, status=400)
            
            # Remove empty strings from lists
            departments = [d.strip() for d in departments if d.strip()]
            sections = [s.strip() for s in sections if s.strip()]
            
            if not departments:
                return JsonResponse({'error': 'At least one department is required'}, status=400)
            
            from core.models import Student, Section, Batch
            
            students = []
            
            for dept_name in departments:
                try:
                    # Get the batch for this department
                    batch = Batch.objects.get(dept__dept_name=dept_name, batch_year=int(batch_year))
                    
                    # If no sections specified, get all sections for this batch
                    if not sections:
                        batch_sections = Section.objects.filter(batch=batch)
                    else:
                        # Filter sections based on provided list
                        section_names = []
                        for section_val in sections:
                            if "-" in section_val:
                                # Format: Department-Section (e.g., "Computer Science-A")
                                dept_part, section_part = section_val.split("-", 1)
                                if dept_part.strip() == dept_name:
                                    section_names.append(section_part.strip())
                            else:
                                # Simple section name (e.g., "A")
                                section_names.append(section_val)
                        
                        if section_names:
                            batch_sections = Section.objects.filter(
                                batch=batch, 
                                section_name__in=section_names
                            )
                        else:
                            batch_sections = Section.objects.filter(batch=batch)
                    
                    # Get students for these sections
                    for section in batch_sections:
                        section_students = Student.objects.filter(section=section).order_by('name')
                        
                        for student in section_students:
                            students.append({
                                'id': student.student_id,
                                'student_id': student.student_id,
                                'name': student.name,
                                'register_number': student.register_number,
                                'department': dept_name,
                                'section': section.section_name,
                                'batch_year': batch_year
                            })
                            
                except Batch.DoesNotExist:
                    continue  # Skip this department if batch not found
                except Exception as e:
                    print(f"Error processing department {dept_name}: {str(e)}")
                    continue
            
            return JsonResponse({
                'students': students,
                'count': len(students)
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
