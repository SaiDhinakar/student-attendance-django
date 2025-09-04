from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse, HttpResponse
from django.contrib import messages
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta
import json
import csv
import io
from django.core.paginator import Paginator
from django.db import transaction
from django.contrib.auth.models import User, Group
from django.contrib.auth.forms import UserCreationForm
from django import forms

from core.models import Student, Department, Batch, Section, Subject, Attendance, Timetable
from .models import Advisor, StaffCreator
from prediction_backend.models import AttendancePrediction, AttendanceSubmission

def get_advisor_profile(user):
    """Get advisor profile or None if user is not an advisor"""
    try:
        return user.advisor_profile
    except:
        return None

def check_advisor_permission(user):
    """Check if user is an advisor - only check group membership, not staff status"""
    # Check if user is in Advisors group OR is superuser (staff users are not allowed)
    is_in_advisor_group = user.groups.filter(name='Advisors').exists()
    
    print(f"DEBUG: User {user.username} - is_in_advisor_group: {is_in_advisor_group}")
    
    return is_in_advisor_group or user.is_superuser

@login_required
def advisor_dashboard(request):
    """Dashboard for advisor users"""
    print(f"DEBUG: User {request.user.username} accessing advisor dashboard")
    print(f"DEBUG: User is_authenticated: {request.user.is_authenticated}")
    print(f"DEBUG: User is_staff: {request.user.is_staff}")
    print(f"DEBUG: User is_superuser: {request.user.is_superuser}")
    
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        print(f"DEBUG: User {request.user.username} denied access to advisor dashboard")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    
    # If user doesn't have advisor profile, show a message but allow access for staff
    if not advisor:
        messages.info(request, "Note: No advisor profile found. Contact admin to create your advisor profile.")
        context = {
            'user': request.user,
            'advisor': None,
            'is_advisor': True,
            'assigned_students': Student.objects.none(),
            'assigned_sections': Section.objects.none(),
            'assigned_departments': Department.objects.none(),
            'assigned_batches': Batch.objects.none(),
            'stats': {
                'total_students': 0,
                'total_sections': 0,
                'total_departments': 0,
                'total_batches': 0,
                'attendance_percentage': 0,
                'today_classes': 0,
            }
        }
        return render(request, 'advisor_dashboard/advisor_dashboard.html', context)
    
    # Get advisor's assigned data
    assigned_students = advisor.get_assigned_students()
    assigned_sections = advisor.get_assigned_sections()
    assigned_departments = advisor.departments.all()
    assigned_batches = advisor.batches.all()
    
    # Calculate attendance statistics
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    # Recent attendance stats
    recent_attendance = Attendance.objects.filter(
        student__in=assigned_students,
        timetable__date__gte=week_ago
    )
    
    total_recent_classes = recent_attendance.count()
    present_count = recent_attendance.filter(is_present=True).count()
    attendance_percentage = (present_count / total_recent_classes * 100) if total_recent_classes > 0 else 0
    
    # Today's classes
    today_timetables = Timetable.objects.filter(
        section__in=assigned_sections,
        date=today
    )
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'is_advisor': True,
        'assigned_students': assigned_students,
        'assigned_sections': assigned_sections,
        'assigned_departments': assigned_departments,
        'assigned_batches': assigned_batches,
        'stats': {
            'total_students': assigned_students.count(),
            'total_sections': assigned_sections.count(),
            'total_departments': assigned_departments.count(),
            'total_batches': assigned_batches.count(),
            'attendance_percentage': round(attendance_percentage, 1),
            'today_classes': today_timetables.count(),
        }
    }
    return render(request, 'advisor_dashboard/advisor_dashboard.html', context)

@login_required
def department_attendance(request):
    """View department attendance for advisors"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    
    if not advisor:
        messages.error(request, "No advisor profile found. Contact admin to create your advisor profile.")
        return redirect("advisor_dashboard:dashboard")
    
    # Get filter parameters
    department_id = request.GET.get('department')
    batch_id = request.GET.get('batch')
    section_id = request.GET.get('section')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Base queryset - only students under this advisor
    students = advisor.get_assigned_students()
    sections = advisor.get_assigned_sections()
    
    # Apply filters
    if department_id:
        sections = sections.filter(batch__dept_id=department_id)
        students = students.filter(section__batch__dept_id=department_id)
    
    if batch_id:
        sections = sections.filter(batch_id=batch_id)
        students = students.filter(section__batch_id=batch_id)
        
    if section_id:
        sections = sections.filter(id=section_id)
        students = students.filter(section_id=section_id)
    
    # Get attendance data
    attendance_query = Attendance.objects.filter(student__in=students)
    
    if date_from:
        attendance_query = attendance_query.filter(timetable__date__gte=date_from)
    if date_to:
        attendance_query = attendance_query.filter(timetable__date__lte=date_to)
    
    # Calculate attendance statistics by section
    section_stats = []
    for section in sections:
        section_students = students.filter(section=section)
        section_attendance = attendance_query.filter(student__in=section_students)
        
        total_classes = section_attendance.count()
        present_count = section_attendance.filter(is_present=True).count()
        percentage = (present_count / total_classes * 100) if total_classes > 0 else 0
        
        section_stats.append({
            'section': section,
            'student_count': section_students.count(),
            'total_classes': total_classes,
            'present_count': present_count,
            'absent_count': total_classes - present_count,
            'percentage': round(percentage, 1)
        })
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'assigned_departments': advisor.departments.all(),
        'assigned_batches': advisor.batches.all(),
        'assigned_sections': advisor.get_assigned_sections(),
        'section_stats': section_stats,
        'filters': {
            'department_id': department_id,
            'batch_id': batch_id,
            'section_id': section_id,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    return render(request, 'advisor_dashboard/department_attendance.html', context)

@login_required
def advisor_attendance_marking(request):
    """Attendance marking for advisors - redirects to shared attendance form"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    
    if not advisor:
        messages.error(request, "No advisor profile found. Contact admin to create your advisor profile.")
        return redirect("advisor_dashboard:dashboard")
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'assigned_departments': advisor.departments.all(),
        'assigned_batches': advisor.batches.all(),
        'assigned_sections': advisor.get_assigned_sections(),
    }
    
    # Use the shared attendance form template
    return render(request, 'shared/attendance_form.html', context)

@login_required
def get_advisor_sections_api(request):
    """API endpoint to get sections for an advisor based on selected department/batch"""
    if not check_advisor_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    advisor = get_advisor_profile(request.user)
    
    if not advisor:
        return JsonResponse({'error': 'No advisor profile found'}, status=404)
    department_id = request.GET.get('department_id')
    batch_id = request.GET.get('batch_id')
    
    sections = advisor.get_assigned_sections()
    
    if department_id:
        sections = sections.filter(batch__dept_id=department_id)
    if batch_id:
        sections = sections.filter(batch_id=batch_id)
    
    sections_data = [
        {
            'id': section.id,
            'name': section.section_name,
            'batch_year': section.batch.year,
            'department': section.batch.dept.dept_name,
            'student_count': section.students.count()
        }
        for section in sections
    ]
    
    return JsonResponse({'sections': sections_data})

@login_required
def advisor_attendance_history(request):
    """View attendance history with detailed analytics"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    
    if not advisor:
        messages.error(request, "No advisor profile found. Contact admin to create your advisor profile.")
        return redirect("advisor_dashboard:dashboard")
    
    # Get recent attendance submissions by this advisor's students
    recent_submissions = AttendanceSubmission.objects.filter(
        student__in=advisor.get_assigned_students()
    ).order_by('-submitted_at')[:20]
    
    # Get recent predictions
    recent_predictions = AttendancePrediction.objects.filter(
        student__in=advisor.get_assigned_students()
    ).order_by('-predicted_at')[:20]
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'recent_submissions': recent_submissions,
        'recent_predictions': recent_predictions,
    }
    
    return render(request, 'advisor_dashboard/attendance_history.html', context)

@login_required
def advisor_reports(request):
    """Reports view for advisors"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    
    if not advisor:
        messages.error(request, "No advisor profile found. Contact admin to create your advisor profile.")
        return redirect("advisor_dashboard:dashboard")
    
    context = {
        'user': request.user,
        'advisor': advisor,
    }
    return render(request, 'advisor_dashboard/reports.html', context)

# STUDENT CRUD OPERATIONS

@login_required
def student_list(request):
    """List all students under advisor's supervision with search and filter"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found. Contact admin to create your advisor profile.")
        return redirect("advisor_dashboard:dashboard")
    
    # Get all students under this advisor (already filtered by advisor's assignments)
    students = advisor.get_assigned_students()
     # Search functionality - only by name and registration number
    search_query = request.GET.get('search')
    if search_query:
        students = students.filter(
            Q(name__icontains=search_query) |
            Q(student_regno__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(students, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Only show advisor's assigned sections for filtering
    assigned_sections = advisor.get_assigned_sections()
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'students': page_obj,
        'assigned_sections': assigned_sections,
        'search_query': search_query,
    }
    return render(request, 'advisor_dashboard/student_list.html', context)

@login_required
def student_detail(request, student_regno):
    """View detailed information about a student"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    # Get student and verify advisor has permission
    student = get_object_or_404(Student, student_regno=student_regno)
    if student not in advisor.get_assigned_students():
        messages.error(request, "You don't have permission to view this student.")
        return redirect("advisor_dashboard:student_list")
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'student': student,
    }
    return render(request, 'advisor_dashboard/student_detail.html', context)

@login_required
def student_create(request):
    """Create a new student (only for assigned sections)"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get the selected section
                section = get_object_or_404(Section, section_id=request.POST['section'])
                
                # Ensure advisor has permission for this section
                if section not in advisor.get_assigned_sections():
                    messages.error(request, "You don't have permission to add students to this section.")
                    return redirect("advisor_dashboard:student_create")
                
                # Create student with department and batch from section
                student = Student.objects.create(
                    student_regno=request.POST['student_regno'],
                    name=request.POST['name'],
                    section=section,
                    department=section.batch.dept,  # Auto-assign from section's batch
                    batch=section.batch,           # Auto-assign from section
                )
                messages.success(request, f"Student {student.name} created successfully!")
                return redirect("advisor_dashboard:student_detail", student_regno=student.student_regno)
        except Exception as e:
            messages.error(request, f"Error creating student: {str(e)}")
    
    # Only show sections that this advisor can manage
    assigned_sections = advisor.get_assigned_sections()
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'assigned_sections': assigned_sections,
    }
    return render(request, 'advisor_dashboard/student_form.html', context)


@login_required
def bulk_student_upload(request):
    """Bulk upload students from CSV file"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    if request.method == 'POST':
        print(f"DEBUG: POST request received")
        print(f"DEBUG: FILES in request: {request.FILES}")
        print(f"DEBUG: POST data: {request.POST}")
        
        if 'csv_file' not in request.FILES:
            print("DEBUG: No csv_file in request.FILES")
            messages.error(request, "Please select a CSV file to upload.")
            return redirect("advisor_dashboard:bulk_student_upload")
        
        csv_file = request.FILES['csv_file']
        print(f"DEBUG: CSV file name: {csv_file.name}")
        print(f"DEBUG: CSV file size: {csv_file.size}")
        
        section_id = request.POST.get('section')
        print(f"DEBUG: Selected section_id: {section_id}")
        
        if not section_id:
            print("DEBUG: No section_id provided")
            messages.error(request, "Please select a section for the students.")
            return redirect("advisor_dashboard:bulk_student_upload")
        
        try:
            print(f"DEBUG: Starting CSV processing...")
            # Get the selected section and validate advisor access
            section = get_object_or_404(Section, section_id=section_id)
            print(f"DEBUG: Found section: {section}")
            if section not in advisor.get_assigned_sections():
                print("DEBUG: Section not in advisor's assigned sections")
                messages.error(request, "You don't have permission to add students to this section.")
                return redirect("advisor_dashboard:bulk_student_upload")
            
            # Read and validate CSV file
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "Please upload a valid CSV file.")
                return redirect("advisor_dashboard:bulk_student_upload")
            
            # Parse CSV content
            decoded_file = csv_file.read().decode('utf-8-sig')  # utf-8-sig automatically removes BOM
            print(f"DEBUG: Decoded file content preview: {decoded_file[:200]}")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            print(f"DEBUG: CSV fieldnames: {reader.fieldnames}")
            
            # Clean fieldnames of any BOM characters (fallback)
            if reader.fieldnames:
                cleaned_fieldnames = [field.lstrip('\ufeff') for field in reader.fieldnames]
                if cleaned_fieldnames != reader.fieldnames:
                    print(f"DEBUG: Cleaned BOM from fieldnames: {cleaned_fieldnames}")
                    reader.fieldnames = cleaned_fieldnames
            
            # Validate required columns
            required_columns = ['student_regno', 'name']
            if not all(col in reader.fieldnames for col in required_columns):
                print(f"DEBUG: Missing columns. Found: {reader.fieldnames}, Required: {required_columns}")
                messages.error(request, f"CSV file must contain columns: {', '.join(required_columns)}")
                return redirect("advisor_dashboard:bulk_student_upload")
            
            created_students = []
            errors = []
            
            print(f"DEBUG: Starting transaction...")
            with transaction.atomic():
                print(f"DEBUG: Entering CSV processing loop...")
                for row_num, row in enumerate(reader, start=2):  # Start from 2 because row 1 is header
                    print(f"DEBUG: Processing row {row_num}: {dict(row)}")
                    student_regno = row.get('student_regno', '').strip()
                    name = row.get('name', '').strip()
                    
                    print(f"DEBUG: Extracted - student_regno: '{student_regno}', name: '{name}'")
                    
                    if not student_regno or not name:
                        error_msg = f"Row {row_num}: Missing student_regno or name"
                        print(f"DEBUG: {error_msg}")
                        errors.append(error_msg)
                        continue
                    
                    # Check if student already exists
                    existing_student = Student.objects.filter(student_regno=student_regno).first()
                    if existing_student:
                        error_msg = f"Row {row_num}: Student {student_regno} already exists"
                        print(f"DEBUG: {error_msg}")
                        errors.append(error_msg)
                        continue
                    
                    try:
                        print(f"DEBUG: Creating student with regno={student_regno}, name={name}, section={section}")
                        # Create student with department and batch from section
                        student = Student.objects.create(
                            student_regno=student_regno,
                            name=name,
                            section=section,
                            department=section.batch.dept,  # Auto-assign from section's batch
                            batch=section.batch,           # Auto-assign from section
                        )
                        print(f"DEBUG: Successfully created student: {student}")
                        created_students.append(student)
                    except Exception as e:
                        error_msg = f"Row {row_num}: Error creating student {student_regno}: {str(e)}"
                        print(f"DEBUG: {error_msg}")
                        errors.append(error_msg)
            
            print(f"DEBUG: Processing complete. Created: {len(created_students)}, Errors: {len(errors)}")
            print(f"DEBUG: Created students: {[str(s) for s in created_students]}")
            print(f"DEBUG: Errors: {errors}")
            
            # Provide feedback
            if created_students:
                success_msg = f"Successfully created {len(created_students)} students."
                print(f"DEBUG: Success message: {success_msg}")
                messages.success(request, success_msg)
            
            if errors:
                # Show first few errors to avoid overwhelming the user
                error_messages = errors[:5]
                if len(errors) > 5:
                    error_messages.append(f"... and {len(errors) - 5} more errors")
                warning_msg = "Some students could not be created: " + "; ".join(error_messages)
                print(f"DEBUG: Warning message: {warning_msg}")
                messages.warning(request, warning_msg)
            
            if not created_students and not errors:
                info_msg = "No valid student data found in the CSV file."
                print(f"DEBUG: Info message: {info_msg}")
                messages.info(request, info_msg)
            
            print(f"DEBUG: Redirecting to student_list...")
            return redirect("advisor_dashboard:student_list")
            
        except Exception as e:
            print(f"DEBUG: Exception in bulk upload: {e}")
            import traceback
            traceback.print_exc()
            messages.error(request, f"Error processing CSV file: {str(e)}")
            return redirect("advisor_dashboard:bulk_student_upload")
    
    # GET request - show upload form
    assigned_sections = advisor.get_assigned_sections()
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'assigned_sections': assigned_sections,
    }
    return render(request, 'advisor_dashboard/bulk_student_upload.html', context)

@login_required
def student_edit(request, student_regno):
    """Edit student information"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    student = get_object_or_404(Student, student_regno=student_regno)
    if student not in advisor.get_assigned_students():
        messages.error(request, "You don't have permission to edit this student.")
        return redirect("advisor_dashboard:student_list")
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                student.name = request.POST['name']
                
                # Only allow changing section if advisor manages both old and new sections
                new_section_id = request.POST.get('section')
                if new_section_id and int(new_section_id) != student.section.section_id:
                    new_section = get_object_or_404(Section, section_id=new_section_id)
                    if new_section in advisor.get_assigned_sections():
                        student.section = new_section
                        # Automatically update department and batch based on new section
                        student.department = new_section.batch.dept
                        student.batch = new_section.batch
                    else:
                        messages.error(request, "You don't have permission to move student to that section.")
                        return redirect("advisor_dashboard:student_edit", student_regno=student_regno)
                
                student.save()
                messages.success(request, f"Student {student.name} updated successfully!")
                return redirect("advisor_dashboard:student_detail", student_regno=student.student_regno)
        except Exception as e:
            messages.error(request, f"Error updating student: {str(e)}")
    
    assigned_sections = advisor.get_assigned_sections()
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'student': student,
        'assigned_sections': assigned_sections,
        'is_edit': True,
    }
    return render(request, 'advisor_dashboard/student_form.html', context)

@login_required
def student_delete(request, student_regno):
    """Delete a student (with confirmation)"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    student = get_object_or_404(Student, student_regno=student_regno)
    if student not in advisor.get_assigned_students():
        messages.error(request, "You don't have permission to delete this student.")
        return redirect("advisor_dashboard:student_list")
    
    if request.method == 'POST':
        try:
            student_name = student.name
            student.delete()
            messages.success(request, f"Student {student_name} deleted successfully!")
            return redirect("advisor_dashboard:student_list")
        except Exception as e:
            messages.error(request, f"Error deleting student: {str(e)}")
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'student': student,
    }
    return render(request, 'advisor_dashboard/student_delete_confirm.html', context)

# ATTENDANCE CRUD OPERATIONS

@login_required
def attendance_list(request):
    """List attendance records with advanced filtering"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    # Base queryset - only attendance for advisor's students
    attendance_records = Attendance.objects.filter(
        student__in=advisor.get_assigned_students()
    ).select_related('student', 'timetable', 'timetable__subject', 'timetable__section')
    
    # Apply filters
    student_regno = request.GET.get('student')
    if student_regno:
        # Verify the student belongs to this advisor
        advisor_students = advisor.get_assigned_students()
        if advisor_students.filter(student_regno=student_regno).exists():
            attendance_records = attendance_records.filter(student__student_regno=student_regno)
    
    subject_id = request.GET.get('subject')
    if subject_id:
        attendance_records = attendance_records.filter(timetable__subject_id=subject_id)
    
    date_from = request.GET.get('date_from')
    if date_from:
        attendance_records = attendance_records.filter(timetable__date__gte=date_from)
    
    date_to = request.GET.get('date_to')
    if date_to:
        attendance_records = attendance_records.filter(timetable__date__lte=date_to)
    
    status = request.GET.get('status')
    if status == 'present':
        attendance_records = attendance_records.filter(is_present=True)
    elif status == 'absent':
        attendance_records = attendance_records.filter(is_present=False)
    
    # Order by date (most recent first)
    attendance_records = attendance_records.order_by('-timetable__date', '-timetable__start_time')
    
    # Pagination
    paginator = Paginator(attendance_records, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'attendance_records': page_obj,
        'assigned_students': advisor.get_assigned_students(),
        'assigned_sections': advisor.get_assigned_sections(),
        'subjects': Subject.objects.all(),
        'filters': {
            'student_regno': student_regno,
            'subject_id': subject_id,
            'date_from': date_from,
            'date_to': date_to,
            'status': status,
        }
    }
    return render(request, 'advisor_dashboard/attendance_list.html', context)

@login_required
def attendance_edit(request, attendance_id):
    """Edit individual attendance record"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    attendance = get_object_or_404(Attendance, attendance_id=attendance_id)
    
    # Verify advisor has permission to edit this attendance
    if attendance.student not in advisor.get_assigned_students():
        messages.error(request, "You don't have permission to edit this attendance record.")
        return redirect("advisor_dashboard:attendance_list")
    
    if request.method == 'POST':
        try:
            attendance.is_present = request.POST.get('is_present') == 'on'
            attendance.save()
            messages.success(request, "Attendance record updated successfully!")
            return redirect("advisor_dashboard:attendance_list")
        except Exception as e:
            messages.error(request, f"Error updating attendance: {str(e)}")
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'attendance': attendance,
    }
    return render(request, 'advisor_dashboard/attendance_edit.html', context)

@login_required
def bulk_attendance_edit(request):
    """Bulk edit attendance for a specific class/timetable"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    timetable_id = request.GET.get('timetable')
    
    if not timetable_id:
        # Show timetable selection page
        # Get recent timetables for advisor's sections
        assigned_sections = advisor.get_assigned_sections()
        available_timetables = Timetable.objects.filter(
            section__in=assigned_sections
        ).order_by('-date', '-start_time')[:50]  # Last 50 classes
        
        context = {
            'user': request.user,
            'advisor': advisor,
            'available_timetables': available_timetables,
        }
        return render(request, 'advisor_dashboard/bulk_attendance_edit.html', context)
    
    timetable = get_object_or_404(Timetable, id=timetable_id)
    
    # Verify advisor has permission for this section
    if timetable.section not in advisor.get_assigned_sections():
        messages.error(request, "You don't have permission to edit attendance for this section.")
        return redirect("advisor_dashboard:attendance_list")
    
    # Get all attendance records for this timetable
    attendance_records = Attendance.objects.filter(timetable=timetable).select_related('student')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                updated_count = 0
                for attendance in attendance_records:
                    field_name = f"attendance_{attendance.attendance_id}"
                    new_status = request.POST.get(field_name) == 'on'
                    if attendance.is_present != new_status:
                        attendance.is_present = new_status
                        attendance.save()
                        updated_count += 1
                
                messages.success(request, f"Updated {updated_count} attendance records!")
                return redirect("advisor_dashboard:attendance_list")
        except Exception as e:
            messages.error(request, f"Error updating attendance: {str(e)}")
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'timetable': timetable,
        'attendance_records': attendance_records,
    }
    return render(request, 'advisor_dashboard/bulk_attendance_edit.html', context)

# STAFF ATTENDANCE TAKING ACCESS

@login_required
@login_required
def staff_attendance_access(request):
    """Allow advisor to access staff attendance taking functionality"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    # Render the same attendance form that staff users see
    context = {
        'user': request.user,
        'advisor': advisor,
        'user_role': 'advisor',
        'base_template': 'advisor_dashboard/advisor_base.html',
        'is_advisor_mode': True,
        'assigned_sections': advisor.get_assigned_sections(),
        'assigned_departments': advisor.departments.all(),
        'assigned_batches': advisor.batches.all(),
    }
    
    return render(request, 'shared/attendance_form.html', context)

# Report views
@login_required
def attendance_reports(request):
    """Main reports dashboard for advisors"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    # Get basic statistics
    assigned_students = advisor.get_assigned_students()
    assigned_sections = advisor.get_assigned_sections()
    
    # Calculate today's attendance
    today = timezone.now().date()
    today_attendance = Attendance.objects.filter(
        student__in=assigned_students,
        timetable__date=today
    )
    
    # Calculate this week's attendance
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    
    week_attendance = Attendance.objects.filter(
        student__in=assigned_students,
        timetable__date__range=[week_start, week_end]
    )
    
    # Calculate this month's attendance
    month_start = today.replace(day=1)
    month_attendance = Attendance.objects.filter(
        student__in=assigned_students,
        timetable__date__gte=month_start
    )
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'assigned_students': assigned_students,
        'assigned_sections': assigned_sections,
        'stats': {
            'total_students': assigned_students.count(),
            'total_sections': assigned_sections.count(),
            'today_classes': today_attendance.count(),
            'today_present': today_attendance.filter(is_present=True).count(),
            'week_classes': week_attendance.count(),
            'week_present': week_attendance.filter(is_present=True).count(),
            'month_classes': month_attendance.count(),
            'month_present': month_attendance.filter(is_present=True).count(),
        }
    }
    return render(request, 'advisor_dashboard/reports/reports_dashboard.html', context)

@login_required
def daily_report(request):
    """Daily attendance report"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    # Get date parameter
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.now().date()
    else:
        selected_date = timezone.now().date()
    
    # Get attendance for the selected date
    attendance_records = Attendance.objects.filter(
        student__in=advisor.get_assigned_students(),
        timetable__date=selected_date
    ).select_related('student', 'timetable', 'timetable__subject', 'timetable__section')
    
    # Group by subject and time
    grouped_attendance = {}
    for record in attendance_records:
        key = f"{record.timetable.subject.subject_name} - {record.timetable.start_time}"
        if key not in grouped_attendance:
            grouped_attendance[key] = {
                'subject': record.timetable.subject,
                'time': record.timetable.start_time,
                'section': record.timetable.section,
                'total': 0,
                'present': 0,
                'absent': 0,
                'records': []
            }
        
        grouped_attendance[key]['total'] += 1
        grouped_attendance[key]['records'].append(record)
        
        if record.is_present:
            grouped_attendance[key]['present'] += 1
        else:
            grouped_attendance[key]['absent'] += 1
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'selected_date': selected_date,
        'grouped_attendance': grouped_attendance,
        'prev_date': selected_date - timedelta(days=1),
        'next_date': selected_date + timedelta(days=1),
    }
    return render(request, 'advisor_dashboard/reports/daily_report.html', context)

@login_required
def weekly_report(request):
    """Weekly attendance report"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    # Get week parameter
    week_str = request.GET.get('week')
    if week_str:
        try:
            selected_date = datetime.strptime(week_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.now().date()
    else:
        selected_date = timezone.now().date()
    
    # Calculate week start and end
    week_start = selected_date - timedelta(days=selected_date.weekday())
    week_end = week_start + timedelta(days=6)
    
    # Get attendance for the week
    attendance_records = Attendance.objects.filter(
        student__in=advisor.get_assigned_students(),
        timetable__date__range=[week_start, week_end]
    ).select_related('student', 'timetable', 'timetable__subject')
    
    # Group by student and day
    student_attendance = {}
    for record in attendance_records:
        student_id = record.student.student_regno
        if student_id not in student_attendance:
            student_attendance[student_id] = {
                'student': record.student,
                'days': {},
                'total_classes': 0,
                'total_present': 0,
            }
        
        day = record.timetable.date.strftime('%A')
        if day not in student_attendance[student_id]['days']:
            student_attendance[student_id]['days'][day] = {'present': 0, 'total': 0}
        
        student_attendance[student_id]['days'][day]['total'] += 1
        student_attendance[student_id]['total_classes'] += 1
        
        if record.is_present:
            student_attendance[student_id]['days'][day]['present'] += 1
            student_attendance[student_id]['total_present'] += 1
    
    # Calculate percentages
    for student_data in student_attendance.values():
        if student_data['total_classes'] > 0:
            student_data['percentage'] = round(
                (student_data['total_present'] / student_data['total_classes']) * 100, 1
            )
        else:
            student_data['percentage'] = 0
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'week_start': week_start,
        'week_end': week_end,
        'student_attendance': student_attendance,
        'prev_week': week_start - timedelta(days=7),
        'next_week': week_start + timedelta(days=7),
        'weekdays': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
    }
    return render(request, 'advisor_dashboard/reports/weekly_report.html', context)

@login_required
def monthly_report(request):
    """Monthly attendance report"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    # Get month parameter
    month_str = request.GET.get('month')
    if month_str:
        try:
            selected_date = datetime.strptime(month_str, '%Y-%m').date()
        except ValueError:
            selected_date = timezone.now().date().replace(day=1)
    else:
        selected_date = timezone.now().date().replace(day=1)
    
    # Calculate month start and end
    month_start = selected_date.replace(day=1)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1) - timedelta(days=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1) - timedelta(days=1)
    
    # Get attendance for the month
    attendance_records = Attendance.objects.filter(
        student__in=advisor.get_assigned_students(),
        timetable__date__range=[month_start, month_end]
    ).select_related('student', 'timetable', 'timetable__subject')
    
    # Group by student
    student_attendance = {}
    for record in attendance_records:
        student_id = record.student.student_regno
        if student_id not in student_attendance:
            student_attendance[student_id] = {
                'student': record.student,
                'total_classes': 0,
                'total_present': 0,
                'subjects': {}
            }
        
        student_attendance[student_id]['total_classes'] += 1
        if record.is_present:
            student_attendance[student_id]['total_present'] += 1
        
        # Track by subject
        subject_name = record.timetable.subject.subject_name
        if subject_name not in student_attendance[student_id]['subjects']:
            student_attendance[student_id]['subjects'][subject_name] = {'present': 0, 'total': 0}
        
        student_attendance[student_id]['subjects'][subject_name]['total'] += 1
        if record.is_present:
            student_attendance[student_id]['subjects'][subject_name]['present'] += 1
    
    # Calculate percentages
    for student_data in student_attendance.values():
        if student_data['total_classes'] > 0:
            student_data['percentage'] = round(
                (student_data['total_present'] / student_data['total_classes']) * 100, 1
            )
        else:
            student_data['percentage'] = 0
        
        # Calculate subject percentages
        for subject_data in student_data['subjects'].values():
            if subject_data['total'] > 0:
                subject_data['percentage'] = round(
                    (subject_data['present'] / subject_data['total']) * 100, 1
                )
            else:
                subject_data['percentage'] = 0
    
    # Calculate previous and next month
    if month_start.month == 1:
        prev_month = month_start.replace(year=month_start.year - 1, month=12)
    else:
        prev_month = month_start.replace(month=month_start.month - 1)
    
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'month_start': month_start,
        'month_end': month_end,
        'student_attendance': student_attendance,
        'prev_month': prev_month,
        'next_month': next_month,
    }
    return render(request, 'advisor_dashboard/reports/monthly_report.html', context)

@login_required
def subject_report(request):
    """Subject-wise attendance report"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    # Get parameters
    subject_id = request.GET.get('subject')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Default date range (last 30 days)
    if not date_from:
        date_from = (timezone.now().date() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_to:
        date_to = timezone.now().date().strftime('%Y-%m-%d')
    
    # Get subjects taught to advisor's students
    subjects = Subject.objects.filter(
        timetable__section__in=advisor.get_assigned_sections()
    ).distinct()
    
    # Build query
    attendance_query = Attendance.objects.filter(
        student__in=advisor.get_assigned_students(),
        timetable__date__range=[date_from, date_to]
    ).select_related('student', 'timetable', 'timetable__subject')
    
    if subject_id:
        attendance_query = attendance_query.filter(timetable__subject_id=subject_id)
    
    attendance_records = attendance_query
    
    # Group with subject and student
    subject_attendance = {}
    for record in attendance_records:
        subject_name = record.timetable.subject.subject_name
        student_id = record.student.student_regno
        
        if subject_name not in subject_attendance:
            subject_attendance[subject_name] = {
                'subject': record.timetable.subject,
                'students': {},
                'total_classes': 0,
                'total_present': 0,
            }
        
        if student_id not in subject_attendance[subject_name]['students']:
            subject_attendance[subject_name]['students'][student_id] = {
                'student': record.student,
                'present': 0,
                'total': 0,
            }
        
        subject_attendance[subject_name]['students'][student_id]['total'] += 1
        subject_attendance[subject_name]['total_classes'] += 1
        
        if record.is_present:
            subject_attendance[subject_name]['students'][student_id]['present'] += 1
            subject_attendance[subject_name]['total_present'] += 1
    
    # Calculate percentages
    for subject_data in subject_attendance.values():
        if subject_data['total_classes'] > 0:
            subject_data['percentage'] = round(
                (subject_data['total_present'] / subject_data['total_classes']) * 100, 1
            )
        else:
            subject_data['percentage'] = 0
        
        for student_data in subject_data['students'].values():
            if student_data['total'] > 0:
                student_data['percentage'] = round(
                    (student_data['present'] / student_data['total']) * 100, 1
                )
            else:
                student_data['percentage'] = 0
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'subjects': subjects,
        'subject_attendance': subject_attendance,
        'selected_subject': subject_id,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'advisor_dashboard/reports/subject_report.html', context)

@login_required
def custom_report(request):
    """Custom attendance report with flexible filters"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    if not advisor:
        messages.error(request, "No advisor profile found.")
        return redirect("advisor_dashboard:dashboard")
    
    # Get filter parameters
    student_regno = request.GET.get('student')
    subject_id = request.GET.get('subject')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    export_format = request.GET.get('export')
    
    # Get available options
    assigned_students = advisor.get_assigned_students()
    subjects = Subject.objects.filter(
        timetable__section__in=advisor.get_assigned_sections()
    ).distinct()
    
    # Build query
    attendance_query = Attendance.objects.filter(
        student__in=assigned_students
    ).select_related('student', 'timetable', 'timetable__subject', 'timetable__section')
    
    # Apply filters
    if student_regno:
        attendance_query = attendance_query.filter(student__student_regno=student_regno)
    
    if subject_id:
        attendance_query = attendance_query.filter(timetable__subject_id=subject_id)
    
    if date_from:
        attendance_query = attendance_query.filter(timetable__date__gte=date_from)
    
    if date_to:
        attendance_query = attendance_query.filter(timetable__date__lte=date_to)
    
    if status == 'present':
        attendance_query = attendance_query.filter(is_present=True)
    elif status == 'absent':
        attendance_query = attendance_query.filter(is_present=False)
    
    attendance_records = attendance_query.order_by('-timetable__date', 'student__name')
    
    # Pagination
    paginator = Paginator(attendance_records, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate summary statistics
    total_records = attendance_records.count()
    present_count = attendance_records.filter(is_present=True).count()
    absent_count = total_records - present_count
    attendance_percentage = (present_count / total_records * 100) if total_records > 0 else 0
    
    context = {
        'user': request.user,
        'advisor': advisor,
        'attendance_records': page_obj,
        'assigned_students': assigned_students,
        'subjects': subjects,
        'filters': {
            'student_regno': student_regno,
            'subject_id': subject_id,
            'date_from': date_from,
            'date_to': date_to,
            'status': status,
        },
        'summary': {
            'total_records': total_records,
            'present_count': present_count,
            'absent_count': absent_count,
            'attendance_percentage': round(attendance_percentage, 1),
        }
    }
    
    # Handle export
    if export_format == 'csv':
        return export_attendance_csv(attendance_records, f"custom_report_{timezone.now().strftime('%Y%m%d')}")
    
    return render(request, 'advisor_dashboard/reports/custom_report.html', context)

def export_attendance_csv(attendance_records, filename):
    """Export attendance records to CSV"""
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Student Registration', 'Student Name', 'Subject', 'Date', 'Time', 
        'Section', 'Status', 'Recorded At'
    ])
    
    for record in attendance_records:
        writer.writerow([
            record.student.student_regno,
            record.student.name,
            record.timetable.subject.subject_name,
            record.timetable.date,
            record.timetable.start_time,
            record.timetable.section.section_name,
            'Present' if record.is_present else 'Absent',
            record.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    return response


@login_required
def subject_create(request):
    """Create new subject for advisor's department/batch"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    
    # Get batches from advisor's assigned students
    advisor_batches = []
    advisor_departments = []
    
    if advisor and advisor.can_view_all_attendance:
        # If advisor can view all attendance, get all batches
        advisor_batches = Batch.objects.all().order_by('dept__dept_name', 'batch_year')
        advisor_departments = Department.objects.all().order_by('dept_name')
    elif advisor:
        # Get batches based on advisor's assigned students
        student_batches = Student.objects.filter(
            section__in=advisor.assigned_sections.all()
        ).values_list('batch', flat=True).distinct()
        
        advisor_batches = Batch.objects.filter(batch_id__in=student_batches).order_by('dept__dept_name', 'batch_year')
        
        # Get departments from these batches
        dept_ids = advisor_batches.values_list('dept', flat=True).distinct()
        advisor_departments = Department.objects.filter(dept_id__in=dept_ids).order_by('dept_name')
    else:
        # For staff users without advisor profile, allow access to all
        advisor_batches = Batch.objects.all().order_by('dept__dept_name', 'batch_year')
        advisor_departments = Department.objects.all().order_by('dept_name')
    
    if request.method == 'POST':
        subject_code = request.POST.get('subject_code', '').strip()
        subject_name = request.POST.get('subject_name', '').strip()
        department_ids = request.POST.getlist('departments')  # Multiple departments
        batch_id = request.POST.get('batch', '').strip()
        
        # Validation
        if not subject_code or not subject_name or not department_ids or not batch_id:
            messages.error(request, "All fields are required.")
        elif Subject.objects.filter(subject_code=subject_code).exists():
            messages.error(request, f"Subject with code '{subject_code}' already exists.")
        elif Subject.objects.filter(subject_name=subject_name).exists():
            messages.error(request, f"Subject with name '{subject_name}' already exists.")
        else:
            try:
                with transaction.atomic():
                    # Get the batch
                    batch = get_object_or_404(Batch, batch_id=batch_id)
                    
                    # Verify advisor has permission for this batch
                    if not advisor or not advisor.can_view_all_attendance:
                        if batch not in advisor_batches:
                            messages.error(request, "You don't have permission to create subjects for this batch.")
                            return render(request, 'advisor_dashboard/subject_create.html', {
                                'departments': advisor_departments,
                                'batches': advisor_batches,
                                'advisor': advisor,
                            })
                    
                    # Create the subject
                    subject = Subject.objects.create(
                        subject_code=subject_code,
                        subject_name=subject_name,
                        batch=batch
                    )
                    
                    # Add selected departments
                    departments = Department.objects.filter(dept_id__in=department_ids)
                    subject.departments.set(departments)
                    
                    messages.success(request, f"Subject '{subject_name}' created successfully!")
                    return redirect('advisor_dashboard:subject_list')
            except Exception as e:
                messages.error(request, f"Error creating subject: {str(e)}")
    
    context = {
        'departments': advisor_departments,
        'batches': advisor_batches,
        'advisor': advisor,
    }
    
    return render(request, 'advisor_dashboard/subject_create.html', context)


@login_required
def subject_list(request):
    """List subjects assigned to advisor's students"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("auth:login")
    
    advisor = get_advisor_profile(request.user)
    
    # Get subjects based on advisor's assigned students
    if advisor and advisor.can_view_all_attendance:
        # If advisor can view all attendance, get all subjects
        subjects = Subject.objects.all().order_by('batch__dept__dept_name', 'batch__batch_year', 'subject_code')
    elif advisor:
        # Get subjects for batches that have students assigned to this advisor
        student_batches = Student.objects.filter(
            section__in=advisor.assigned_sections.all()
        ).values_list('batch', flat=True).distinct()
        
        subjects = Subject.objects.filter(
            batch__batch_id__in=student_batches
        ).order_by('batch__dept__dept_name', 'batch__batch_year', 'subject_code')
    else:
        # For staff users without advisor profile, show all subjects
        subjects = Subject.objects.all().order_by('batch__dept__dept_name', 'batch__batch_year', 'subject_code')
    
    # Search functionality
    search_query = request.GET.get('search', '').strip()
    if search_query:
        subjects = subjects.filter(
            Q(subject_code__icontains=search_query) |
            Q(subject_name__icontains=search_query) |
            Q(departments__dept_name__icontains=search_query)
        ).distinct()
    
    # Pagination
    paginator = Paginator(subjects, 20)
    page_number = request.GET.get('page')
    subjects_paginated = paginator.get_page(page_number)
    
    # Calculate statistics
    all_subjects = subjects  # Keep the queryset for statistics
    total_departments = all_subjects.values('departments').distinct().count()
    total_batches = all_subjects.values('batch').distinct().count()
    
    context = {
        'subjects': subjects_paginated,
        'search_query': search_query,
        'advisor': advisor,
        'total_departments': total_departments,
        'total_batches': total_batches,
    }


# Staff Management Views
@login_required
def staff_list(request):
    """View to list all staff users"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect('auth:login')
    
    # Get all staff users (either in Staffs group or with is_staff=True but not in Advisors group)
    staffs_group = Group.objects.filter(name='Staffs').first()
    advisors_group = Group.objects.filter(name='Advisors').first()
    
    if staffs_group:
        staff_users = User.objects.filter(
            Q(groups=staffs_group) | 
            (Q(is_staff=True) & ~Q(groups=advisors_group) & ~Q(is_superuser=True))
        ).distinct().order_by('username')
    else:
        staff_users = User.objects.filter(
            is_staff=True, 
            is_superuser=False
        ).exclude(
            groups=advisors_group
        ).order_by('username')
    
    # Get the creator information for each staff user
    staff_creators = {
        sc.staff_user_id: sc 
        for sc in StaffCreator.objects.filter(
            staff_user__in=staff_users
        ).select_related('created_by')
    }
    
    context = {
        'staff_users': staff_users,
        'staff_creators': staff_creators,
        'title': 'Staff Management',
    }
    return render(request, 'advisor_dashboard/staff_list.html', context)


class StaffUserForm(forms.ModelForm):
    """Form for creating and updating staff users"""
    password = forms.CharField(widget=forms.PasswordInput(), required=False,
                              help_text="Leave empty to keep current password")
    confirm_password = forms.CharField(widget=forms.PasswordInput(), required=False)
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active']
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match')
        
        return cleaned_data


@login_required
def staff_create(request):
    """View to create a new staff user"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect('auth:login')
    
    if request.method == 'POST':
        form = StaffUserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            password = form.cleaned_data['password']
            if password:
                user.set_password(password)
            user.is_staff = True
            user.save()
            
            # Add user to Staffs group
            staffs_group, created = Group.objects.get_or_create(name='Staffs')
            user.groups.add(staffs_group)
            
            # Create a StaffCreator record to track who created this staff
            StaffCreator.objects.create(
                staff_user=user,
                created_by=request.user
            )
            
            messages.success(request, f"Staff user '{user.username}' created successfully")
            return redirect('advisor_dashboard:staff_list')
    else:
        form = StaffUserForm()
    
    context = {
        'form': form,
        'title': 'Create Staff User',
        'submit_text': 'Create Staff',
    }
    return render(request, 'advisor_dashboard/staff_form.html', context)


@login_required
def staff_edit(request, user_id):
    """View to edit a staff user"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect('auth:login')
    
    try:
        staff_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "Staff user not found")
        return redirect('advisor_dashboard:staff_list')
    
    # Check if this is an advisor or superuser
    if staff_user.groups.filter(name='Advisors').exists() or staff_user.is_superuser:
        messages.error(request, "Cannot edit advisor or admin users through this interface")
        return redirect('advisor_dashboard:staff_list')
    
    if request.method == 'POST':
        form = StaffUserForm(request.POST, instance=staff_user)
        if form.is_valid():
            user = form.save(commit=False)
            password = form.cleaned_data['password']
            if password:
                user.set_password(password)
            user.is_staff = True  # Ensure they remain staff
            user.save()
            
            # Ensure they're in Staffs group
            staffs_group, created = Group.objects.get_or_create(name='Staffs')
            user.groups.add(staffs_group)
            
            messages.success(request, f"Staff user '{user.username}' updated successfully")
            return redirect('advisor_dashboard:staff_list')
    else:
        form = StaffUserForm(instance=staff_user)
    
    context = {
        'form': form,
        'staff_user': staff_user,
        'title': f'Edit Staff User: {staff_user.username}',
        'submit_text': 'Update Staff',
    }
    return render(request, 'advisor_dashboard/staff_form.html', context)


@login_required
def staff_delete(request, user_id):
    """View to delete a staff user"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect('auth:login')
    
    try:
        staff_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "Staff user not found")
        return redirect('advisor_dashboard:staff_list')
    
    # Check if this is an advisor or superuser
    if staff_user.groups.filter(name='Advisors').exists() or staff_user.is_superuser:
        messages.error(request, "Cannot delete advisor or admin users through this interface")
        return redirect('advisor_dashboard:staff_list')
    
    if request.method == 'POST':
        username = staff_user.username
        staff_user.delete()
        messages.success(request, f"Staff user '{username}' deleted successfully")
        return redirect('advisor_dashboard:staff_list')
    
    context = {
        'staff_user': staff_user,
        'title': f'Delete Staff User: {staff_user.username}',
        'confirmation_message': f'Are you sure you want to delete the staff user "{staff_user.username}"?',
    }
    return render(request, 'advisor_dashboard/staff_delete_confirm.html', context)


@login_required
def staff_toggle_active(request, user_id):
    """AJAX view to toggle a staff user's active status"""
    if not check_advisor_permission(request.user) or request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    try:
        staff_user = User.objects.get(id=user_id)
        
        # Check if this is an advisor or superuser
        if staff_user.groups.filter(name='Advisors').exists() or staff_user.is_superuser:
            return JsonResponse({'success': False, 'error': 'Cannot modify advisor or admin users'}, status=403)
        
        staff_user.is_active = not staff_user.is_active
        staff_user.save()
        
        return JsonResponse({
            'success': True, 
            'is_active': staff_user.is_active,
            'message': f"User {staff_user.username} {'activated' if staff_user.is_active else 'deactivated'} successfully"
        })
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return render(request, 'advisor_dashboard/subject_list.html', context)
