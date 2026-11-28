from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from projects.models import Project
from tasks.models import Task

def login_view(request):
    error = None
    if request.method == "POST":
        user = authenticate(request, email=request.POST["email"], password=request.POST["password"])
        if user:
            login(request, user)
            return redirect(request.GET.get("next", "/"))
        error = "Invalid email or password"
    return render(request, "login.html", {"error": error})

def logout_view(request):
    if request.method == "POST":
        logout(request)
    return redirect("/login/")

@login_required
def dashboard(request):
    tasks = Task.objects.for_user(request.user)
    return render(request, "dashboard.html", {
        "stats": {"open": tasks.open().count(), "overdue": tasks.overdue().count(),
                  "due_soon": tasks.due_soon().count()},
        "overdue_list": tasks.overdue().select_related("project")[:5],
        "projects": Project.objects.filter(memberships__user=request.user).distinct()[:6]
                    | Project.objects.filter(owner=request.user)[:6],
    })

@login_required
def project_list(request):
    u = request.user
    qs = Project.objects.all() if u.role == "Admin" else (
        Project.objects.filter(memberships__user=u) | Project.objects.filter(owner=u)).distinct()
    return render(request, "projects.html", {"projects": qs})