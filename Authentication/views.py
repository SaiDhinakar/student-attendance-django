from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render

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
    return redirect("/auth/login/")


@login_required
def dashboard(request):
    """Redirect to appropriate dashboard based on user role and group"""
    redirect_url = get_user_redirect_url(request.user)
    return redirect(redirect_url)