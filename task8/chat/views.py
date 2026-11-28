from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .consumers import HISTORY_LIMIT, MAX_MESSAGE_LENGTH
from .forms import RoomForm, SignupForm
from .models import Presence, Room


def signup(request):
    if request.user.is_authenticated:
        return redirect("lobby")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("lobby")
    return render(request, "registration/signup.html", {"form": form})


@login_required
def lobby(request):
    form = RoomForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        room, _ = Room.objects.get_or_create(
            name=form.cleaned_data["name"], defaults={"created_by": request.user}
        )
        return redirect("room", room_name=room.name)

    rooms = list(Room.objects.select_related("created_by").annotate(message_count=Count("messages")))
    online = dict(
        Presence.objects.values("room_id")
        .annotate(n=Count("user", distinct=True))
        .values_list("room_id", "n")
    )
    for room in rooms:
        room.online = online.get(room.id, 0)
    return render(request, "chat/lobby.html", {"form": form, "rooms": rooms})


@login_required
def room(request, room_name):
    room = get_object_or_404(Room, name=room_name)
    return render(
        request,
        "chat/room.html",
        {"room": room, "max_length": MAX_MESSAGE_LENGTH, "history_limit": HISTORY_LIMIT},
    )
