from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render

from .forms import DigestPreferenceForm
from .models import DigestPreference, ExchangeRate
from .services import sync_digest_task


@login_required
def digest_settings(request):
    pref = DigestPreference.objects.filter(user=request.user).first()
    form = DigestPreferenceForm(request.POST or None, instance=pref)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            pref = form.save(commit=False)
            pref.user = request.user
            pref.save()
            sync_digest_task(pref)
        messages.success(request, "Digest preferences saved.")
        return redirect("automation:settings")
    return render(request, "automation/settings.html", {
        "form": form,
        "pref": pref,
        "rates": ExchangeRate.objects.all(),
        "tz": settings.TIME_ZONE,
    })
