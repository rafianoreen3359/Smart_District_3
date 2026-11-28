from django import forms

from .models import DigestPreference


class DigestPreferenceForm(forms.ModelForm):
    send_time = forms.TimeField(
        label="Send my digest at",
        input_formats=["%H:%M", "%H:%M:%S"],
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
    )
    enabled = forms.BooleanField(required=False, label="Email me a daily digest")

    class Meta:
        model = DigestPreference
        fields = ["send_time", "enabled"]
