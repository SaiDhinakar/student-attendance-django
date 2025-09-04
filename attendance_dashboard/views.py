from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.contrib import messages

def check_staff_permission(user, allow_advisors=False):
    """Check if user has staff permissions (either Staffs group or general staff without advisor permissions)"""
    if user.is_superuser:
        return False  # Superusers should use admin panel
    
    # Allow advisors if explicitly permitted (for advisor dashboard access)
    if allow_advisors and user.groups.filter(name='Advisors').exists():
        return True
    
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
            return redirect("auth:login")
    
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
    # Check if this is an advisor accessing through the advisor dashboard
    is_advisor_access = (request.user.groups.filter(name='Advisors').exists() and 
                        request.META.get('HTTP_REFERER', '').find('/advisor/') != -1)
    
    if not check_staff_permission(request.user, allow_advisors=is_advisor_access):
        if request.user.is_superuser:
            messages.error(request, "Access denied. Admins should use the admin panel.")
            return redirect("admin:index")
        elif request.user.groups.filter(name='Advisors').exists() and not is_advisor_access:
            messages.error(request, "Access denied. Advisors should use the advisor dashboard.")
            return redirect("advisor_dashboard:dashboard")
        else:
            messages.error(request, "Access denied. You don't have staff permissions.")
            return redirect("auth:login")
    
    # Determine user role and base template
    if request.user.groups.filter(name='Advisors').exists():
        user_role = 'advisor'
        base_template = 'advisor_dashboard/advisor_base.html'
        user_group = 'Advisor'
    else:
        user_role = 'staff'
        base_template = 'attendance_dashboard/staff_base.html'
        user_group = 'Staffs' if request.user.groups.filter(name='Staffs').exists() else 'General Staff'
    
    context = {
        'user': request.user,
        'user_role': user_role,
        'base_template': base_template,
        'user_department': None,  # Can access all departments
        'user_group': user_group,
    }
    return render(request, 'shared/attendance_form.html', context)

@login_required
def reports_view(request):
    """View for attendance reports"""
    # Check if this is an advisor accessing through the advisor dashboard
    is_advisor_access = (request.user.groups.filter(name='Advisors').exists() and 
                        request.META.get('HTTP_REFERER', '').find('/advisor/') != -1)
    
    if not check_staff_permission(request.user, allow_advisors=is_advisor_access):
        if request.user.is_superuser:
            messages.error(request, "Access denied. Admins should use the admin panel.")
            return redirect("admin:index")
        elif request.user.groups.filter(name='Advisors').exists() and not is_advisor_access:
            messages.error(request, "Access denied. Advisors should use the advisor dashboard.")
            return redirect("advisor_dashboard:dashboard")
        else:
            messages.error(request, "Access denied. You don't have staff permissions.")
            return redirect("auth:login")
    
    # Only general staff can access reports, not Staffs group (unless advisor)
    if request.user.groups.filter(name='Staffs').exists() and not is_advisor_access:
        messages.error(request, "Access denied. Staff members can only mark attendance.")
        return redirect("attendance_dashboard:attendance")
    
    # Determine user role and base template
    if request.user.groups.filter(name='Advisors').exists():
        user_role = 'advisor'
        base_template = 'advisor_dashboard/advisor_base.html'
    else:
        user_role = 'staff'
        base_template = 'attendance_dashboard/staff_base.html'
    
    context = {
        'user': request.user,
    }
    return render(request, 'attendance_dashboard/reports.html', context)

@login_required
def camera_attendance_view(request):
    """View for camera-based attendance taking"""
    # Check if this is an advisor accessing through the advisor dashboard
    is_advisor_access = (request.user.groups.filter(name='Advisors').exists() and 
                        request.META.get('HTTP_REFERER', '').find('/advisor/') != -1)
    
    if not check_staff_permission(request.user, allow_advisors=is_advisor_access):
        if request.user.is_superuser:
            messages.error(request, "Access denied. Admins should use the admin panel.")
            return redirect("admin:index")
        elif request.user.groups.filter(name='Advisors').exists() and not is_advisor_access:
            messages.error(request, "Access denied. Advisors should use the advisor dashboard.")
            return redirect("advisor_dashboard:dashboard")
        else:
            messages.error(request, "Access denied. You don't have staff permissions.")
            return redirect("auth:login")
    
    # Determine user role and base template
    if request.user.groups.filter(name='Advisors').exists():
        user_role = 'advisor'
        base_template = 'advisor_dashboard/advisor_base.html'
        user_group = 'Advisor'
    else:
        user_role = 'staff'
        base_template = 'attendance_dashboard/staff_base.html'
        user_group = 'Staffs' if request.user.groups.filter(name='Staffs').exists() else 'General Staff'
    
    context = {
        'user': request.user,
        'user_role': user_role,
        'is_staff': request.user.is_staff and not request.user.groups.filter(name='Advisors').exists(),
        'base_template': base_template,
        'user_department': None,  # Can access all departments
        'user_group': user_group,
    }
    return render(request, 'shared/attendance_taking.html', context)
