from io import BytesIO
from typing import Any

from django.test import TestCase

from .models import Client, Shipment
from .services import process_shipments_txt


class ProcessShipmentsTxtTests(TestCase):
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

		self.assertEqual(result, {"created": 3, "updated": 0, "errors": []})
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

# Create your tests here.
