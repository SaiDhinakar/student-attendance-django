from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render
from core.models import Department, Student, Subject, Batch

def get_user_redirect_url(user):
    """Determine redirect URL based on user role and group membership"""
    if user.is_superuser:
        return "admin:index"
    elif user.groups.filter(name='Advisors').exists():
        return "advisor_dashboard:dashboard"
    elif user.groups.filter(name='Staffs').exists():
        return "attendance_dashboard:attendance"  # Staff goes directly to attendance marking
    else:
        # Default for staff users without specific group
        return "attendance_dashboard:dashboard"

# Create your views here.
def login_view(request):
    if request.user.is_authenticated:
        # Redirect based on user role and group
        redirect_url = get_user_redirect_url(request.user)
        return redirect(redirect_url)

    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Logged in successfully")
            
            # Redirect based on user role and group
            if next_url:
                return redirect(next_url)
            else:
                redirect_url = get_user_redirect_url(user)
                return redirect(redirect_url)
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "authentication/login.html", {"next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out")
    return redirect("auth:login")


@login_required
def dashboard(request):
    """Redirect to appropriate dashboard based on user role and group"""
    redirect_url = get_user_redirect_url(request.user)
    return redirect(redirect_url)


def notification_test(request):
    """Test page for notification system"""
    # Add test messages when requested
    if request.GET.get('test_messages'):
        messages.success(request, 'This is a test success message that will disappear in 3 seconds!')
        messages.error(request, 'This is a test error message that will disappear in 3 seconds!')
        messages.warning(request, 'This is a test warning message that will disappear in 3 seconds!')
        messages.info(request, 'This is a test info message that will disappear in 3 seconds!')
    
    return render(request, 'notification_test.html')


@login_required
def departments_view(request):
    departments = Department.objects.all()
    return render(request, "authentication/departments.html", {"departments": departments})


@login_required
def students_view(request):
    students = Student.objects.select_related('department', 'batch').all()
    departments = Department.objects.all()
    return render(request, "authentication/students.html", {
        "students": students,
        "departments": departments
    })


@login_required
def subjects_view(request):
    subjects = Subject.objects.select_related('department').all()
    departments = Department.objects.all()
    return render(request, "authentication/subjects.html", {
        "subjects": subjects,
        "departments": departments
    })


@login_required
def batches_view(request):
    batches = Batch.objects.select_related('department').prefetch_related('student_set').all()
    departments = Department.objects.all()
    return render(request, "authentication/batches.html", {
        "batches": batches,
        "departments": departments
    })