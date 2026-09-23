from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0003_alter_shipment_remito_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="client",
            name="password_hash",
            field=models.CharField(
                blank=True,
                default="",
                max_length=128,
                verbose_name="Contraseña cifrada",
            ),
        ),
    ]