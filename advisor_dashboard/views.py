from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib import messages

def check_advisor_permission(user):
    """Check if user is an advisor"""
    return user.is_staff and user.groups.filter(name='Advisors').exists()

@login_required
def advisor_dashboard(request):
    """Dashboard for advisor users"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("login")
    
    context = {
        'user': request.user,
        'is_advisor': True,
    }
    return render(request, 'advisor_dashboard/advisor_dashboard.html', context)

@login_required
def department_attendance(request):
    """View department attendance for advisors"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("login")
    
    context = {
        'user': request.user,
    }
    return render(request, 'advisor_dashboard/department_attendance.html', context)

@login_required
def advisor_attendance_marking(request):
    """Attendance marking for advisors"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("login")
    
    # Get user's department (this could be stored in user profile or groups)
    # For now, we'll assume it's stored in user profile or can be determined
    user_department = getattr(request.user, 'department', None)  # You might need to add this field
    
    context = {
        'user': request.user,
        'user_role': 'advisor',
        'base_template': 'advisor_dashboard/advisor_base.html',
        'user_department': user_department,  # Advisors are restricted to their department
    }
    return render(request, 'shared/attendance_form.html', context)

@login_required
def advisor_reports(request):
    """Reports view for advisors"""
    if not check_advisor_permission(request.user):
        messages.error(request, "Access denied. You don't have advisor permissions.")
        return redirect("login")
    
    context = {
        'user': request.user,
    }
    return render(request, 'advisor_dashboard/reports.html', context)
