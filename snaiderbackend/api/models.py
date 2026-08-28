from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator, RegexValidator

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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['name']

    def __str__(self) -> str:
        return f"{str(self.name)} ({str(self.dni_cuit)})"


class Shipment(models.Model):
    """
    Representa cada despacho o remito cargado en el sistema.
    """
    # Identificación única del remito
    remito_number = models.CharField(
        max_length=50,
        unique=True,
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

    def __str__(self):
        return f"Remito #{self.remito_number} - {self.recipient.name}"