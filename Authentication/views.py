from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import redirect, render

# Create your views here.
def login_view(request):
    if request.user.is_authenticated:
        return redirect("admin:index")

    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Logged in successfully")
            return redirect(next_url or "admin:index")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "authentication/login.html", {"next": next_url})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out")
    return redirect("login")


@login_required
def dashboard(request):
    """Redirect to Django admin dashboard"""
    return redirect("admin:index")