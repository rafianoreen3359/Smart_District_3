from django.contrib import admin
from .models import PageView, EventLog

admin.site.register(PageView)
admin.site.register(EventLog)