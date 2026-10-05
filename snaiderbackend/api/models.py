from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.db.models import UniqueConstraint
from django.core.validators import MinValueValidator, RegexValidator
from django.utils.timezone import get_current_timezone, is_naive, make_aware

# Create your models here.
class Client(models.Model):
    """
    Representa al Consignatario (Cliente que recibe y consulta por DNI/CUIT).
    """
    dni_cuit = models.CharField(
        max_length=11,
        unique=True,
        db_index=True,
        validators=[
            RegexValidator(
                regex=r"^(\d{8}|\d{11})$",
                message="Debe contener exactamente 8 u 11 dígitos.",
            )
        ],
        verbose_name="DNI o CUIT"
    )
    name = models.CharField(
        max_length=255,
        verbose_name="Nombre / Razón Social"
    )
    password_hash = models.CharField(
        max_length=128,
        blank=True,
        default="",
        verbose_name="Contraseña cifrada",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['name']

    def __str__(self) -> str:
        return f"{str(self.name)} ({str(self.dni_cuit)})" # type: ignore

    def set_password(self, raw_password: str) -> None:
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password_hash) # type: ignore


class Shipment(models.Model):
    """
    Representa cada despacho o remito cargado en el sistema.
    """
    # Identificación única del remito
    remito_number = models.CharField(
        max_length=50,
        db_index=True,
        verbose_name="N° de Remito"
    )

    # Relaciones y Actores
    sender = models.CharField(
        max_length=255,
        verbose_name="Remitente"
    )
    recipient = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="shipments",
        verbose_name="Consignatario (Cliente)"
    )

    # Ubicación y Logística
    deposit_number = models.CharField(
        max_length=100,
        verbose_name="N° Depósito / Destino"
    )
    logistics_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Logística / Transporte interno"
    )

    # Métricas de la Carga
    packages = models.IntegerField(
        validators=[MinValueValidator(0)],
        default=1,
        verbose_name="Bultos"
    )
    weight_kg= models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Peso (Kgs)"
    )
    declared_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Valor Declarado"
    )
    value_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Tipo de Valor"
    )

    # Fechas y Estado
    received_datetime = models.DateTimeField(
        verbose_name="Fecha y Hora de Recibido"
    )
    received_date = models.DateField(
        editable=False,
        verbose_name="Fecha de Recibido (derivada)",
        help_text="Se deriva de received_datetime y forma parte de la clave única.",
    )
    observations = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observaciones"
    )

    # Control del Registro
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Despacho / Remito"
        verbose_name_plural = "Despachos / Remitos"
        ordering = ['-received_datetime']
        constraints = [
            UniqueConstraint(
                fields=["remito_number", "recipient", "received_date"],
                name="uniq_shipment_remito_recipient_date",
            ),
        ]

    def __str__(self):
        return f"Remito #{self.remito_number} - {self.recipient.name}" # type: ignore

    @staticmethod
    def resolve_received_date(value: datetime) -> date:
        """
        Reduce un instante a la fecha de negocio en la zona horaria activa.

        Es la única fuente de verdad para la clave de duplicados. Antes esta fecha
        se recalculaba en cada consulta, de modo que el mismo TXT podía generar
        claves distintas según la zona horaria activa en el momento de leer.
        """
        tz = get_current_timezone()
        if is_naive(value):
            value = make_aware(value, tz)
        return value.astimezone(tz).date()

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.received_datetime is not None:
            self.received_date = self.resolve_received_date(self.received_datetime)
        super().save(*args, **kwargs)