from django.contrib import admin, messages
from .models import Client, Shipment
from .services import generate_client_password


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
	list_display = ("dni_cuit", "name", "created_at", "updated_at")
	search_fields = ("dni_cuit", "name")
	readonly_fields = ("password_hash", "created_at", "updated_at")
	actions = ("regenerate_one_password",)

	@admin.action(description="Regenerar contraseña de un cliente")
	def regenerate_one_password(self, request, queryset):
		if queryset.count() != 1:
			self.message_user(
				request,
				"Seleccioná exactamente un cliente.",
				level=messages.ERROR,
			)
			return

		client = queryset.first()
		password = generate_client_password()
		client.set_password(password)
		client.save(update_fields=["password_hash", "updated_at"])
		self.message_user(
			request,
			f"Nueva contraseña para {client.dni_cuit}: {password}",
			level=messages.SUCCESS,
		)


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
	list_display = ("remito_number", "recipient", "received_datetime")
	search_fields = ("remito_number", "recipient__dni_cuit", "recipient__name")
