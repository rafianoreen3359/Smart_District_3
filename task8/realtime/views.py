from django.shortcuts import render

from .consumers import MAX_MESSAGE_LENGTH


def index(request):
    return render(request, "realtime/index.html", {"max_length": MAX_MESSAGE_LENGTH})
