from typing import Any

from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import Token

from .models import Client


class ClientJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token: Token) -> Client:
        if validated_token.get("user_type") != "client":
            raise AuthenticationFailed("El token no pertenece a un cliente.")

        client_id: Any = validated_token.get("client_id")
        try:
            return Client.objects.get(pk=client_id)
        except Client.DoesNotExist as exc:
            raise AuthenticationFailed("El cliente del token ya no existe.") from exc