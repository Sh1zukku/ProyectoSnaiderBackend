from typing import Any, cast

from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.throttling import AnonRateThrottle
from .models import Client, Shipment
from .serializers import (
    ClientAdminSerializer,
    FileUploadSerializer,
    ShipmentAdminSerializer,
    ShipmentPublicSerializer,
)
from .services import generate_client_password, process_shipments_txt


class ClientSearchThrottle(AnonRateThrottle):
    """Limita a los clientes a 10 consultas por minuto por dirección IP"""
    rate = '10/minute'


class ClientShipmentSearchView(APIView):
    """
    Endpoint PÚBLICO para que el cliente consulte sus remitos por DNI/CUIT.
    GET /api/v1/shipments/search/?dni_cuit=43235050
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ClientSearchThrottle]

    def post(self, request: Request):
        dni_cuit = str(request.data.get('dni_cuit', '')).strip()
        password = str(request.data.get('password', ''))

        if not dni_cuit or not password:
            return Response(
                {"error": "Debe proporcionar CUIT/DNI y contraseña."},
                status=status.HTTP_400_BAD_REQUEST
            )

        client = get_object_or_404(Client, dni_cuit=dni_cuit)
        if not client.check_password(password):
            return Response(
                {"error": "CUIT/DNI o contraseña incorrectos."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Búsqueda optimizada aprovechando la relación e índice
        shipments = Shipment.objects.filter(
            recipient__dni_cuit=dni_cuit
        ).select_related('recipient').order_by('-received_datetime')

        serializer = ShipmentPublicSerializer(shipments, many=True)

        serialized_data: list[dict[str, Any]] = cast(
            list[dict[str, Any]],
            cast(Any, serializer).data,
        )

        return Response({
            "count": shipments.count(),
            "results": serialized_data,
        })


class ClientChangePasswordView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request: Request) -> Response:
        dni_cuit = str(request.data.get('dni_cuit', '')).strip()
        current_password = str(request.data.get('current_password', ''))
        new_password = str(request.data.get('new_password', ''))

        if not dni_cuit or not current_password or not new_password:
            return Response(
                {"error": "Debe proporcionar CUIT/DNI, contraseña actual y nueva."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(new_password) < 8:
            return Response(
                {"error": "La nueva contraseña debe tener al menos 8 caracteres."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        client = get_object_or_404(Client, dni_cuit=dni_cuit)
        if not client.check_password(current_password):
            return Response(
                {"error": "La contraseña actual es incorrecta."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        client.set_password(new_password)
        client.save(update_fields=["password_hash", "updated_at"])
        return Response({"message": "Contraseña actualizada correctamente."})


class AdminUploadTxtView(APIView):
    """
    Endpoint PROTEGIDO para que solo el Admin suba la planilla TXT.
    POST /api/v1/admin/upload-txt/
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request: Request) -> Response:
        serializer = FileUploadSerializer(data=request.data)

        if serializer.is_valid():
            uploaded_file = serializer.validated_data["file"]
            result = process_shipments_txt(uploaded_file)

            return Response(
                {
                    "message": "Archivo procesado con éxito.",
                    "details": result,
                },
                status=status.HTTP_200_OK,
            )

        errors: Any = cast(Any, serializer.errors)
        return Response(
            errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class AdminRegenerateClientPasswordView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request: Request, client_id: int) -> Response:
        client = get_object_or_404(Client, pk=client_id)
        password = generate_client_password()
        client.set_password(password)
        client.save(update_fields=["password_hash", "updated_at"])
        return Response({
            "dni_cuit": client.dni_cuit,
            "name": client.name,
            "password": password,
        })


class AdminClientListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request: Request) -> Response:
        clients = Client.objects.all().order_by("name")
        serializer = ClientAdminSerializer(clients, many=True)
        return Response({
            "count": clients.count(),
            "results": serializer.data,
        })


class AdminShipmentListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request: Request) -> Response:
        shipments = Shipment.objects.select_related("recipient").all()
        shipments = shipments.order_by("-received_datetime")
        serializer = ShipmentAdminSerializer(shipments, many=True)
        return Response({
            "count": shipments.count(),
            "results": serializer.data,
        })