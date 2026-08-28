from typing import Any, cast

from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.throttling import AnonRateThrottle
from .models import Shipment
from .serializers import ShipmentPublicSerializer, FileUploadSerializer
from .services import process_shipments_txt


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

    def get(self, request: Request):
        dni_cuit = request.query_params.get('dni_cuit', '').strip()

        if not dni_cuit:
            return Response(
                {"error": "Debe proporcionar un parámetro 'dni_cuit'."},
                status=status.HTTP_400_BAD_REQUEST
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