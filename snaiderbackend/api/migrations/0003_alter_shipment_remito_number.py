from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0002_alter_shipment_value_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="shipment",
            name="remito_number",
            field=models.CharField(
                db_index=True,
                max_length=50,
                verbose_name="N° de Remito",
            ),
        ),
    ]