import csv
import re
import secrets
from datetime import datetime
from io import StringIO
from typing import Any, BinaryIO, cast
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils.timezone import get_current_timezone, make_aware
from .models import Client, Shipment


LINE_PATTERN = re.compile(
    r"^\s*"
    r"(?P<remito>\S+)\s+"
    r"(?P<sender>.*?)\s{2,}"
    r"(?P<recipient>.*?)\s{2,}"
    r"(?P<deposit>.*?)\s{2,}"
    r"(?P<packages>\d+)\s+"
    r"(?P<weight>\d+(?:[.,]\d+)?)\s+"
    r"(?P<value>\d+(?:[.,]\d+)?)\s+"
    r"(?P<type_observations>.*?)\s{2,}"
    r"(?P<received>\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2})\s{2,}"
    r"(?P<logistics>\S+)(?:\s+|\t+)"
    r"(?P<dni_cuit>\d{8}|\d{11})\s*$"
)


OBSERVATION_CORRECTIONS = {
    "O-Flete Or gen": "O-Flete Orígen",
}


def generate_client_password() -> str:
    return secrets.token_urlsafe(9)


def build_credentials_csv(accounts: list[dict[str, str]]) -> str:
    output = StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["dni_cuit", "name", "password"],
    )
    writer.writeheader()
    writer.writerows(accounts)
    return output.getvalue()


def process_shipments_txt(file_obj: BinaryIO) -> dict[str, Any]:
    """
    Procesa un archivo TXT cargado y guarda/actualiza los clientes y envíos en la BD.
    Usa atomic transaction para revertir cambios si ocurre un error grave.
    """
    lines = file_obj.read().decode('utf-8', errors='ignore').splitlines()
    created_count = 0
    updated_count = 0
    errors: list[str] = []
    new_accounts: list[dict[str, str]] = []

    with transaction.atomic():
        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            if not line:
                continue

            match = LINE_PATTERN.match(line)
            if not match:
                errors.append(f"Línea {line_num}: Formato inválido o faltan campos.")
                continue

            try:
                data = match.groupdict()
                remito_num = data["remito"].strip()
                sender = data["sender"].strip()
                recipient_name = data["recipient"].strip()
                deposit = data["deposit"].strip()
                packages = int(data["packages"])
                weight = data["weight"].replace(",", ".")
                declared_val = data["value"].replace(",", ".")
                dni_cuit = data["dni_cuit"]

                type_observations = data["type_observations"].strip()
                type_observations = OBSERVATION_CORRECTIONS.get(
                    type_observations,
                    type_observations,
                )
                type_parts = type_observations.split(maxsplit=1)
                value_type = type_parts[0] if type_parts else None
                observations = type_observations or None
                naive_dt = datetime.strptime(data["received"], "%d/%m/%Y %H:%M")
                received_dt = make_aware(naive_dt, get_current_timezone())

                # 1. Buscar o Crear el Cliente
                client_password = generate_client_password()
                client, client_created = Client.objects.get_or_create(
                    dni_cuit=dni_cuit,
                    defaults={
                        'name': recipient_name,
                        'password_hash': make_password(client_password),
                    }
                )

                if client_created:
                    new_accounts.append({
                        "dni_cuit": dni_cuit,
                        "name": recipient_name,
                        "password": client_password,
                    })

                # 2. Ignorar el registro solo si coinciden remito, cliente y fecha.
                duplicate = Shipment.objects.filter(
                    remito_number=remito_num,
                    recipient=client,
                    received_datetime__date=received_dt.date(),
                ).exists()

                if duplicate:
                    continue

                # Actualizar el nombre solo cuando la fila genera un envío nuevo.
                if cast(Any, client).name != recipient_name:
                    client.name = recipient_name
                    client.save()

                Shipment.objects.create(
                    remito_number=remito_num,
                    sender=sender,
                    recipient=client,
                    deposit_number=deposit,
                    packages=packages,
                    weight_kg=weight,
                    declared_value=declared_val,
                    value_type=value_type,
                    received_datetime=received_dt,
                    logistics_id=data["logistics"],
                    observations=observations,
                )
                created_count += 1

            except Exception as e:
                errors.append(f"Línea {line_num}: Error procesando datos - {str(e)}")

    return {
        "created": created_count,
        "updated": updated_count,
        "errors": errors,
        "new_accounts": new_accounts,
        "credentials_csv": build_credentials_csv(new_accounts),
    }