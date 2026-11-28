from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.text import slugify


class RoomForm(forms.Form):
    name = forms.CharField(
        max_length=50,
        label="Room name",
        widget=forms.TextInput(attrs={"placeholder": "design-team", "autocomplete": "off"}),
        help_text="Letters, numbers and hyphens. If the room exists you will join it.",
    )

    def clean_name(self):
        slug = slugify(self.cleaned_data["name"], allow_unicode=False)[:50].strip("-")
        if not slug:
            raise forms.ValidationError("Use at least one letter or number.")
        return slug


class SignupForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username",)
