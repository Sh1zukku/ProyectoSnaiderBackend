from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from .models import Client


class IsAuthenticatedClient(BasePermission):
    def has_permission(self, request: Request, view: Any) -> bool:
        return isinstance(request.user, Client)