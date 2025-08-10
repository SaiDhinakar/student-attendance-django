from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta
import json

from core.models import Student, Department, Batch, Section, Subject, Attendance, Timetable
from .models import Advisor
from prediction_backend.models import AttendancePrediction, AttendanceSubmission

def get_advisor_profile(user):
    """Get advisor profile or None if user is not an advisor"""
    try:
        return user.advisor_profile
    except:
        return None

def check_advisor_permission(user):
    """Check if user is an advisor - check both group membership and staff status"""
    # Check if user is in Advisors group OR is staff (for development)
    is_in_advisor_group = user.groups.filter(name='Advisors').exists()
    is_staff_user = user.is_staff
    
    print(f"DEBUG: User {user.username} - is_in_advisor_group: {is_in_advisor_group}, is_staff: {is_staff_user}")
    
    return is_in_advisor_group or is_staff_user or user.is_superuser

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
        return redirect("/auth/login/")
    
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
        return redirect("login")
    
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
        return redirect("login")
    
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
        return redirect("login")
    
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
        return redirect("login")
    
    advisor = get_advisor_profile(request.user)
    
    if not advisor:
        messages.error(request, "No advisor profile found. Contact admin to create your advisor profile.")
        return redirect("advisor_dashboard:dashboard")
    
    context = {
        'user': request.user,
        'advisor': advisor,
    }
    return render(request, 'advisor_dashboard/reports.html', context)
