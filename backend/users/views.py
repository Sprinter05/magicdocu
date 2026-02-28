from django.shortcuts import redirect, render

from .forms import RegisterForm


def sign_up(request):
    if request.method == "GET":
        form = RegisterForm()
        return render(request, "signup.html", {"form": form})
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            return redirect("login")
        else:
            return render(request, "signup.html", {"form": form})