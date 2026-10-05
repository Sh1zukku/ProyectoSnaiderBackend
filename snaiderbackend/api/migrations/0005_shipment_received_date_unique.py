import re

from django.db import migrations, models
from django.utils import timezone as dj_timezone


DEDUPE_BATCH_SIZE = 1000


def _batch(values, size):
    values = list(values)
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _local_date(received_datetime):
    return received_datetime.astimezone(dj_timezone.get_current_timezone()).date()


def normalize_remito_numbers(apps, schema_editor):
    """
    Lleva los remitos existentes a la forma normalizada que usa el servicio.

    Se ejecuta antes del dedupe a propósito: si "10001" y "10001 " conviven,
    normalizar primero es lo que hace que el dedupe los vea como el mismo grupo.
    """
    Shipment = apps.get_model("api", "Shipment")
    db_alias = schema_editor.connection.alias
    whitespace = re.compile(r"\s+")

    pending = []
    for pk, remito_number in Shipment.objects.using(db_alias).order_by("pk").values_list(
        "pk", "remito_number"
    ).iterator(chunk_size=DEDUPE_BATCH_SIZE):
        if remito_number == whitespace.sub(" ", remito_number).strip():
            continue
        pending.append(Shipment(pk=pk, remito_number=whitespace.sub(" ", remito_number).strip()))
        if len(pending) >= DEDUPE_BATCH_SIZE:
            Shipment.objects.using(db_alias).bulk_update(
                pending, ["remito_number"], batch_size=DEDUPE_BATCH_SIZE
            )
            pending = []

    if pending:
        Shipment.objects.using(db_alias).bulk_update(
            pending, ["remito_number"], batch_size=DEDUPE_BATCH_SIZE
        )


def dedupe_shipments(apps, schema_editor):
    """
    Deja un solo Shipment por (remito_number, recipient_id, received_datetime.date),
    conservando el de created_at más antiguo.

    La fecha se calcula en Python replicando Shipment.resolve_received_date para no
    depender del estado del modelo en este punto de la migración.
    """
    Shipment = apps.get_model("api", "Shipment")
    db_alias = schema_editor.connection.alias

    seen = set()
    duplicates = []
    queryset = (
        Shipment.objects.using(db_alias)
        .order_by("created_at", "pk")
        .values_list("pk", "remito_number", "recipient_id", "received_datetime")
    )

    for pk, remito_number, recipient_id, received_datetime in queryset.iterator(
        chunk_size=DEDUPE_BATCH_SIZE
    ):
        key = (remito_number, recipient_id, _local_date(received_datetime))
        if key in seen:
            duplicates.append(pk)
        else:
            seen.add(key)

    deleted = 0
    for batch in _batch(duplicates, DEDUPE_BATCH_SIZE):
        count, _ = Shipment.objects.using(db_alias).filter(pk__in=batch).delete()
        deleted += count

    if deleted:
        print(f"[0005] Se eliminaron {deleted} shipments duplicados antes de aplicar la unicidad.")


def backfill_received_date(apps, schema_editor):
    Shipment = apps.get_model("api", "Shipment")
    db_alias = schema_editor.connection.alias

    queryset = (
        Shipment.objects.using(db_alias)
        .order_by("pk")
        .values_list("pk", "received_datetime")
    )

    for batch in _batch(queryset.iterator(chunk_size=DEDUPE_BATCH_SIZE), DEDUPE_BATCH_SIZE):
        updates = [
            Shipment(pk=pk, received_date=_local_date(received_datetime))
            for pk, received_datetime in batch
        ]

        Shipment.objects.using(db_alias).bulk_update(
            updates, ["received_date"], batch_size=DEDUPE_BATCH_SIZE
        )


def noop(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0004_client_password_hash"),
    ]

    operations = [
        migrations.RunPython(normalize_remito_numbers, noop),
        migrations.RunPython(dedupe_shipments, noop),
        migrations.AddField(
            model_name="shipment",
            name="received_date",
            field=models.DateField(
                default=None,
                editable=False,
                help_text="Se deriva de received_datetime y forma parte de la clave única.",
                null=True,
                verbose_name="Fecha de Recibido (derivada)",
            ),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_received_date, noop),
        migrations.AlterField(
            model_name="shipment",
            name="received_date",
            field=models.DateField(
                editable=False,
                help_text="Se deriva de received_datetime y forma parte de la clave única.",
                verbose_name="Fecha de Recibido (derivada)",
            ),
        ),
        migrations.AddConstraint(
            model_name="shipment",
            constraint=models.UniqueConstraint(
                fields=("remito_number", "recipient", "received_date"),
                name="uniq_shipment_remito_recipient_date",
            ),
        ),
    ]