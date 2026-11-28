from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

class TeamHubTokenSerializer(TokenObtainPairSerializer):
    username_field = "email"

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["full_name"] = user.full_name
        token["role"] = user.role
        token["is_admin"] = user.role == "Admin"
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = {"id": self.user.id, "email": self.user.email, "role": self.user.role}
        return data

class TeamHubTokenView(TokenObtainPairView):
    serializer_class = TeamHubTokenSerializer