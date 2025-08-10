from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib import messages

def check_staff_permission(user):
    """Check if user has staff permissions (either Staffs group or general staff without advisor permissions)"""
    if user.is_superuser:
        return False  # Superusers should use admin panel
    
    # Allow Staffs group members or staff users without Advisors group
    return (user.is_staff and user.groups.filter(name='Staffs').exists()) or \
           (user.is_staff and not user.groups.filter(name='Advisors').exists())

@login_required
def staff_dashboard(request):
    """Dashboard for staff users (non-admin users)"""
    if not check_staff_permission(request.user):
        if request.user.is_superuser:
            messages.error(request, "Access denied. Admins should use the admin panel.")
            return redirect("admin:index")
        elif request.user.groups.filter(name='Advisors').exists():
            messages.error(request, "Access denied. Advisors should use the advisor dashboard.")
            return redirect("advisor_dashboard:dashboard")
        else:
            messages.error(request, "Access denied. You don't have staff permissions.")
            return redirect("login")
    
    # If user is in Staffs group, redirect to attendance marking
    if request.user.groups.filter(name='Staffs').exists():
        return redirect("attendance_dashboard:attendance")
    
    context = {
        'user': request.user,
        'is_staff': request.user.is_staff,
    }
    return render(request, 'attendance_dashboard/staff_dashboard.html', context)

@login_required
def attendance_view(request):
    """View for managing attendance"""
    if not check_staff_permission(request.user):
        if request.user.is_superuser:
            messages.error(request, "Access denied. Admins should use the admin panel.")
            return redirect("admin:index")
        elif request.user.groups.filter(name='Advisors').exists():
            messages.error(request, "Access denied. Advisors should use the advisor dashboard.")
            return redirect("advisor_dashboard:dashboard")
        else:
            messages.error(request, "Access denied. You don't have staff permissions.")
            return redirect("login")
    
    context = {
        'user': request.user,
        'user_role': 'staff',
        'base_template': 'attendance_dashboard/staff_base.html',
        'user_department': None,  # Staff can access all departments
        'user_group': 'Staffs' if request.user.groups.filter(name='Staffs').exists() else 'General Staff',
    }
    return render(request, 'shared/attendance_form.html', context)

@login_required
def reports_view(request):
    """View for attendance reports"""
    if not check_staff_permission(request.user):
        if request.user.is_superuser:
            messages.error(request, "Access denied. Admins should use the admin panel.")
            return redirect("admin:index")
        elif request.user.groups.filter(name='Advisors').exists():
            messages.error(request, "Access denied. Advisors should use the advisor dashboard.")
            return redirect("advisor_dashboard:dashboard")
        else:
            messages.error(request, "Access denied. You don't have staff permissions.")
            return redirect("login")
    
    # Only general staff can access reports, not Staffs group
    if request.user.groups.filter(name='Staffs').exists():
        messages.error(request, "Access denied. Staff members can only mark attendance.")
        return redirect("attendance_dashboard:attendance")
    
    context = {
        'user': request.user,
    }
    return render(request, 'attendance_dashboard/reports.html', context)

@login_required
def camera_attendance_view(request):
    """View for camera-based attendance taking"""
    if not check_staff_permission(request.user):
        if request.user.is_superuser:
            messages.error(request, "Access denied. Admins should use the admin panel.")
            return redirect("admin:index")
        elif request.user.groups.filter(name='Advisors').exists():
            messages.error(request, "Access denied. Advisors should use the advisor dashboard.")
            return redirect("advisor_dashboard:dashboard")
        else:
            messages.error(request, "Access denied. You don't have staff permissions.")
            return redirect("login")
    
    context = {
        'user': request.user,
        'user_role': 'staff',
        'base_template': 'attendance_dashboard/staff_base.html',
        'user_department': None,  # Staff can access all departments
        'user_group': 'Staffs' if request.user.groups.filter(name='Staffs').exists() else 'General Staff',
    }
    return render(request, 'shared/attendance_taking.html', context)
