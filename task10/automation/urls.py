from django.urls import path

from . import views

app_name = "automation"
urlpatterns = [path("settings/digest/", views.digest_settings, name="settings")]
