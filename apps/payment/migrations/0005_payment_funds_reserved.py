from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("payment", "0004_alter_config_id_alter_payment_status")]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="funds_reserved",
            field=models.BooleanField(default=False, editable=False, verbose_name="Funds reserved"),
        ),
    ]
