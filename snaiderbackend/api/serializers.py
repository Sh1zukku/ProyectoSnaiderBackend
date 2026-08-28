from typing import Any

from rest_framework import serializers
from .models import Client, Shipment


class ClientPublicSerializer(serializers.ModelSerializer[Client]):
    class Meta:
        model = Client
        fields = ['dni_cuit', 'name']


class ShipmentPublicSerializer(serializers.ModelSerializer[Shipment]):
    """Información que verá el cliente al consultar por DNI/CUIT."""

    recipient = ClientPublicSerializer(read_only=True)

    class Meta:
        model = Shipment
        fields = [
            "remito_number",
            "sender",
            "recipient",
            "deposit_number",
            "packages",
            "weight_kg",
            "declared_value",
            "received_datetime",
            "observations",
        ]


class FileUploadSerializer(serializers.Serializer[dict[str, Any]]):
    """Serializador para validar el archivo subido por el admin."""

    file = serializers.FileField()

    def validate_file(self, value: Any) -> Any:
        if not value.name.lower().endswith(".txt"):
            raise serializers.ValidationError(
                "Solo se permiten archivos de texto (.txt)."
            )
        return value