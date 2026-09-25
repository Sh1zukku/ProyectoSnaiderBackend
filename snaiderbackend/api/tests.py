from io import BytesIO
from datetime import datetime, timedelta
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Client, Shipment
from .services import process_shipments_txt


class ProcessShipmentsTxtTests(TestCase):
	def test_ignores_only_same_remito_client_and_date(self):
		content = (
			"10001 REMITENTE                    DESTINATARIO UNO            "
			"06 RESISTENCIA          1      1.00       100.00 N                    "
			"                    20/08/2026 10:00  1  24349012\n"
			"10001 REMITENTE                    DESTINATARIO UNO            "
			"06 RESISTENCIA          2      2.00       200.00 N                    "
			"                    20/08/2026 11:00  1  24349012\n"
			"10001 REMITENTE                    DESTINATARIO DOS            "
			"06 RESISTENCIA          3      3.00       300.00 N                    "
			"                    20/08/2026 12:00  1  23452342\n"
			"10001 REMITENTE                    DESTINATARIO UNO            "
			"06 RESISTENCIA          4      4.00       400.00 N                    "
			"                    21/08/2026 10:00  1  24349012"
		).encode("utf-8")

		result = process_shipments_txt(BytesIO(content))

		self.assertEqual(result["created"], 3)
		self.assertEqual(result["updated"], 0)
		self.assertEqual(result["errors"], [])
		self.assertEqual(len(result["new_accounts"]), 2)
		self.assertEqual(Shipment.objects.count(), 3)
		self.assertEqual(
			set(Shipment.objects.values_list("recipient__dni_cuit", flat=True)),
			{"24349012", "23452342"},
		)

	def test_processes_fixed_width_lines_and_preserves_all_fields(self):
		content = (
			"          38503 ARGENTAGRO S.R.L.         AGRO CHACO SRL            "
			"06 RESISTENCIA          3      0.00    293917.00 N                    "
			"                    20/08/2026 18:14  1\t24349012\n"
			"     3400044703 CELSUR LOGISTICA S.A.     DALLAS MOTORS SA          "
			"06 RESISTENCIA          3      0.00         0.00 O-Flete Or gen       "
			"                    20/08/2026 18:27  1  23452342\n"
			"           50000 REMITENTE                    DESTINATARIO              "
			"06 RESISTENCIA          1      2.50      1000.00 X-Carga Peligrosa      "
			"                    21/08/2026 12:00  1  24349013"
		).encode("utf-8")

		result = process_shipments_txt(BytesIO(content))

		self.assertEqual(result["created"], 3)
		self.assertEqual(result["updated"], 0)
		self.assertEqual(result["errors"], [])
		self.assertEqual(len(result["new_accounts"]), 3)
		self.assertEqual(Client.objects.count(), 3)
		self.assertEqual(Shipment.objects.count(), 3)

		shipment: Any = Shipment.objects.get(remito_number="3400044703")
		self.assertEqual(shipment.recipient.dni_cuit, "23452342")
		self.assertEqual(shipment.logistics_id, "1")
		self.assertEqual(shipment.value_type, "O-Flete")
		self.assertEqual(shipment.observations, "O-Flete Orígen")

		standard_shipment: Any = Shipment.objects.get(remito_number="38503")
		self.assertEqual(standard_shipment.value_type, "N")
		self.assertEqual(standard_shipment.observations, "N")

		dangerous_shipment: Any = Shipment.objects.get(remito_number="50000")
		self.assertEqual(dangerous_shipment.value_type, "X-Carga")
		self.assertEqual(dangerous_shipment.observations, "X-Carga Peligrosa")


class AdminDeleteOldShipmentsTests(TestCase):
	def setUp(self):
		self.client_api = APIClient()
		user_model = cast(Any, get_user_model())
		self.admin = user_model.objects.create_superuser(
			username="admin",
			password="admin-password",
			email="admin@example.com",
		)
		self.recipient = Client.objects.create(
			dni_cuit="24349012",
			name="Cliente de prueba",
		)

	def create_shipment(self, created_at: datetime) -> Shipment:
		shipment = Shipment.objects.create(
			remito_number=f"R-{created_at.timestamp()}",
			sender="Remitente",
			recipient=self.recipient,
			deposit_number="06",
			received_datetime=created_at,
			created_at=created_at,
		)
		Shipment.objects.filter(pk=shipment.pk).update(created_at=created_at)
		return shipment

	def test_admin_deletes_shipments_older_than_requested_days(self):
		now = timezone.now()
		old_shipment = self.create_shipment(now - timedelta(days=8))
		recent_shipment = self.create_shipment(now - timedelta(days=2))
		self.client_api.force_authenticate(user=self.admin)

		response = self.client_api.post(
			"/api/admin/shipments/delete-old/",
			{"days": 7},
			format="json",
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["deleted_count"], 1)
		self.assertFalse(Shipment.objects.filter(pk=old_shipment.pk).exists())
		self.assertTrue(Shipment.objects.filter(pk=recent_shipment.pk).exists())

	def test_days_must_be_positive(self):
		self.client_api.force_authenticate(user=self.admin)

		response = self.client_api.post(
			"/api/admin/shipments/delete-old/",
			{"days": 0},
			format="json",
		)

		self.assertEqual(response.status_code, 400)

	def test_non_admin_cannot_delete_shipments(self):
		user_model = cast(Any, get_user_model())
		user = user_model.objects.create_user(
			username="user",
			password="user-password",
		)
		self.client_api.force_authenticate(user=user)

		response = self.client_api.post(
			"/api/admin/shipments/delete-old/",
			{"days": 7},
			format="json",
		)

		self.assertEqual(response.status_code, 403)

# Create your tests here.
