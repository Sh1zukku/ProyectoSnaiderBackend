import csv
import re
import secrets
from datetime import date, datetime
from io import StringIO
from typing import Any, BinaryIO
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, transaction
from django.utils.timezone import make_aware
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

WHITESPACE_RE = re.compile(r"\s+")

SHIPMENT_BATCH_SIZE = 1000


def normalize_remito(value: str) -> str:
    """
    Reduce un N° de remito a una forma comparable.

    El TXT y la base pueden diferir en espacios sobrantes, y sin esta normalización
    "10001" y "10001 " son claves distintas: el duplicado pasa el filtro en memoria
    y la restricción de la base no lo frena porque compara el texto crudo.
    """
    return WHITESPACE_RE.sub(" ", value).strip()


def generate_client_password() -> str:
    return secrets.token_urlsafe(9)

def build_credentials_csv(accounts: list[dict[str, str]]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["dni_cuit", "name", "password"])
    writer.writeheader()
    writer.writerows(accounts)
    return output.getvalue()

def _row_received_date(received: str) -> date:
    """Fecha de negocio de una fila del TXT, en la zona horaria activa."""
    naive_dt = datetime.strptime(received, "%d/%m/%Y %H:%M")
    return Shipment.resolve_received_date(make_aware(naive_dt))


def _load_duplicate_keys(parsed_rows: list[dict[str, Any]], client_ids: list[int]) -> set[tuple[str, int, date]]:
    """
    Carga desde la base solo las claves que el archivo podría volver a generar.

    received_date se lee de la columna materializada en lugar de recalcular
    received_datetime__date, de modo que la clave no dependa de la zona horaria
    activa en el momento de la consulta.
    """
    if not client_ids:
        return set()

    remitos = {normalize_remito(str(row["remito"])) for row in parsed_rows}
    dates = [
        _row_received_date(str(row["received"]))
        for row in parsed_rows
    ]

    if not remitos or not dates:
        return set()

    return {
        (normalize_remito(remito_number), recipient_id, received_date)
        for remito_number, recipient_id, received_date in Shipment.objects.filter(
            recipient_id__in=client_ids,
            remito_number__in=remitos,
            received_date__range=(min(dates), max(dates)),
        ).values_list("remito_number", "recipient_id", "received_date")
    }


def build_duplicate_key(remito_number: str, recipient_id: int, shipment_date: date) -> tuple[str, int, date]:
    """Clave que debe coincidir con la restricción uniq_shipment_remito_recipient_date."""
    return (normalize_remito(remito_number), recipient_id, shipment_date)


def _persist_shipments(rows: list[tuple[Shipment, int]]) -> tuple[int, int, list[str]]:
    """
    Inserta los envíos y devuelve (creados, omitidos_por_duplicado, errores).

    Cada fila es (shipment, line_num) para poder ubicar el error en el TXT.

    El camino rápido es un único bulk_create dentro de un savepoint. Si la base
    rechaza alguna fila, se reintenta una por una para no perder el resto de la
    carga: el duplicado se cuenta como omitido en vez de abortar la transacción.
    """
    try:
        with transaction.atomic():
            Shipment.objects.bulk_create(
                [shipment for shipment, _ in rows], batch_size=SHIPMENT_BATCH_SIZE
            )
        return len(rows), 0, []
    except IntegrityError:
        pass

    created = 0
    duplicates = 0
    write_errors: list[str] = []

    for shipment, line_num in rows:
        try:
            with transaction.atomic():
                shipment.save()
            created += 1
        except IntegrityError:
            duplicates += 1
        except Exception as e:
            write_errors.append(f"Línea {line_num}: Error guardando envío - {str(e)}")

    return created, duplicates, write_errors


def process_shipments_txt(file_obj: BinaryIO) -> dict[str, Any]:
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
        return {
            "created": 0,
            "updated": 0,
            "skipped_duplicates": 0,
            "errors": errors,
            "new_accounts": [],
            "credentials_csv": "",
        }

    with transaction.atomic():
        # 2. Carga en bloque de Clientes Existentes (Evita N+1 Queries)
        existing_clients = {
            c.dni_cuit: c for c in Client.objects.filter(dni_cuit__in=dnis_in_file) # pyright: ignore[reportUnknownMemberType]
        }
        
        new_clients_to_create: list[Client] = []
        new_accounts: list[dict[str, str]] = []
        queued_client_dnis: set[str] = set()

        # Identificar clientes que realmente deben crearse
        for data in parsed_rows:
            dni = data["dni_cuit"]
            if dni in existing_clients or dni in queued_client_dnis:
                continue

            pwd = generate_client_password()
            recipient_name = data["recipient"].strip()

            client_obj = Client(
                dni_cuit=dni,
                name=recipient_name,
                password_hash=make_password(pwd)  # Solo se ejecuta para clientes verdaderamente NUEVOS
            )
            new_clients_to_create.append(client_obj)
            queued_client_dnis.add(dni)
            new_accounts.append({
                "dni_cuit": dni,
                "name": recipient_name,
                "password": pwd,
            })

        # Inserción masiva de clientes
        if new_clients_to_create:
            Client.objects.bulk_create(new_clients_to_create)
            # Re-consultar los recién creados para obtener sus IDs asignados por la BD
            created_clients = Client.objects.filter(dni_cuit__in=queued_client_dnis) # pyright: ignore[reportUnknownMemberType]
            for c in created_clients:
                existing_clients[c.dni_cuit] = c # pyright: ignore[reportUnknownMemberType]

        # 3. Cacheo de Envíos Existentes para la clave (remito + cliente_id + fecha)
        # Se filtran por los remitos del archivo y el rango de fechas presente: traer
        # todo el historial de cada cliente es inviable a escala y no aporta nada.
        client_ids = [c.id for c in existing_clients.values()] # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        existing_shipments_tuples = _load_duplicate_keys(parsed_rows, client_ids) # pyright: ignore[reportUnknownArgumentType]

        shipments_to_create: list[tuple[Shipment, int]] = []
        skipped_duplicates = 0

        for data in parsed_rows:
            try:
                dni = data["dni_cuit"]
                client = existing_clients[dni]
                remito_num = normalize_remito(data["remito"])

                naive_dt = datetime.strptime(data["received"], "%d/%m/%Y %H:%M")
                received_dt = make_aware(naive_dt)
                shipment_date = Shipment.resolve_received_date(received_dt)

                # Validación de duplicados en memoria O(1), con la misma clave que
                # la restricción de la base. La base sigue siendo la autoridad: esto
                # solo evita el viaje innecesario.
                composite_key = build_duplicate_key(remito_num, client.id, shipment_date) # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType, reportAttributeAccessIssue]
                if composite_key in existing_shipments_tuples:
                    skipped_duplicates += 1
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
                    received_date=shipment_date,
                    logistics_id=data["logistics"],
                    observations=observations,
                )

                shipments_to_create.append((shipment, int(data['line_num'])))
                # Agregar al set local para evitar duplicados repetidos dentro del mismo TXT
                existing_shipments_tuples.add(composite_key)

            except Exception as e:
                errors.append(f"Línea {data['line_num']}: Error procesando datos - {str(e)}")

        # Inserción masiva. bulk_create no setea received_date (no llama save()), y
        # dos cargas simultáneas pueden chocar contra la restricción entre la
        # lectura del set y esta escritura: por eso el fallback fila por fila.
        created_count = 0
        if shipments_to_create:
            created_count, write_duplicates, write_errors = _persist_shipments(shipments_to_create)
            skipped_duplicates += write_duplicates
            errors.extend(write_errors)

    return {
        "created": created_count,
        "updated": 0,
        "skipped_duplicates": skipped_duplicates,
        "errors": errors,
        "new_accounts": new_accounts,
        "credentials_csv": build_credentials_csv(new_accounts),
    }