import csv
import re
import secrets
from datetime import datetime
from io import StringIO
from typing import Any, BinaryIO
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
    writer = csv.DictWriter(output, fieldnames=["dni_cuit", "name", "password"])
    writer.writeheader()
    writer.writerows(accounts)
    return output.getvalue()

def process_shipments_txt(file_obj: BinaryIO) -> dict[str, Any]:
    tz = get_current_timezone()
    errors: list[str] = []
    
    # 1. Parseo inicial en memoria
    parsed_rows: list[dict[str, Any]] = []
    dnis_in_file: set[str] = set()
    
    for line_num, line in enumerate(file_obj, start=1):
        try:
            decoded_line = line.decode('utf-8', errors='ignore').strip()
        except Exception:
            continue
            
        if not decoded_line:
            continue

        match = LINE_PATTERN.match(decoded_line)
        if not match:
            errors.append(f"Línea {line_num}: Formato inválido o faltan campos.")
            continue

        data = match.groupdict()
        data['line_num'] = line_num
        parsed_rows.append(data)
        dnis_in_file.add(data["dni_cuit"])

    if not parsed_rows:
        return {"created": 0, "updated": 0, "errors": errors, "new_accounts": [], "credentials_csv": ""}

    with transaction.atomic():
        # 2. Carga en bloque de Clientes Existentes (Evita N+1 Queries)
        existing_clients = {
            c.dni_cuit: c for c in Client.objects.filter(dni_cuit__in=dnis_in_file) # pyright: ignore[reportUnknownMemberType]
        }
        
        new_clients_to_create: list[Client] = []
        new_accounts: list[dict[str, str]] = []
        
        # Identificar clientes que realmente deben crearse
        for data in parsed_rows:
            dni = data["dni_cuit"]
            if dni not in existing_clients and dni not in [c.dni_cuit for c in new_clients_to_create]: # pyright: ignore[reportUnknownMemberType]
                pwd = generate_client_password()
                recipient_name = data["recipient"].strip()
                
                client_obj = Client(
                    dni_cuit=dni,
                    name=recipient_name,
                    password_hash=make_password(pwd)  # Solo se ejecuta para clientes verdaderamente NUEVOS
                )
                new_clients_to_create.append(client_obj)
                new_accounts.append({
                    "dni_cuit": dni,
                    "name": recipient_name,
                    "password": pwd,
                })

        # Inserción masiva de clientes
        if new_clients_to_create:
            Client.objects.bulk_create(new_clients_to_create)
            # Re-consultar los recién creados para obtener sus IDs asignados por la BD
            created_clients = Client.objects.filter(dni_cuit__in=[c.dni_cuit for c in new_clients_to_create]) # pyright: ignore[reportUnknownMemberType]
            for c in created_clients:
                existing_clients[c.dni_cuit] = c # pyright: ignore[reportUnknownMemberType]

        # 3. Cacheo de Envíos Existentes para Clave Compleja (remito + cliente_id + fecha)
        # Traemos envíos que puedan coincidir para validar duplicados localmente
        client_ids = [c.id for c in existing_clients.values()] # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        existing_shipments_tuples = set(
            Shipment.objects.filter(recipient_id__in=client_ids)
            .values_list('remito_number', 'recipient_id', 'received_datetime__date')
        )

        shipments_to_create: list[Shipment] = []
        created_count = 0

        for data in parsed_rows:
            try:
                dni = data["dni_cuit"]
                client = existing_clients[dni]
                remito_num = data["remito"].strip()
                
                naive_dt = datetime.strptime(data["received"], "%d/%m/%Y %H:%M")
                received_dt = make_aware(naive_dt, tz)
                shipment_date = received_dt.date()

                # Validación de duplicados en Memoria O(1)
                composite_key = (remito_num, client.id, shipment_date) # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
                if composite_key in existing_shipments_tuples:
                    continue

                # Preparar normalización de observaciones
                type_obs = (data.get("type_observations") or "").strip()
                type_obs = OBSERVATION_CORRECTIONS.get(type_obs, type_obs)
                type_parts = type_obs.split(maxsplit=1) if type_obs else []

                value_type = type_parts[0] if type_parts else None
                observations = type_obs or None

                shipment = Shipment(
                    remito_number=remito_num,
                    sender=data["sender"].strip(),
                    recipient=client,
                    deposit_number=data["deposit"].strip(),
                    packages=int(data["packages"]),
                    weight_kg=data["weight"].replace(",", "."),
                    declared_value=data["value"].replace(",", "."),
                    value_type=value_type,
                    received_datetime=received_dt,
                    logistics_id=data["logistics"],
                    observations=observations,
                )
                
                shipments_to_create.append(shipment)
                # Agregar al set local para evitar duplicados repetidos dentro del mismo TXT
                existing_shipments_tuples.add(composite_key)
                created_count += 1

            except Exception as e:
                errors.append(f"Línea {data['line_num']}: Error procesando datos - {str(e)}")

        # Inserción masiva de envíos en 1 sola consulta SQL
        if shipments_to_create:
            Shipment.objects.bulk_create(shipments_to_create, batch_size=1000)

    return {
        "created": created_count,
        "updated": 0,
        "errors": errors,
        "new_accounts": new_accounts,
        "credentials_csv": build_credentials_csv(new_accounts),
    }