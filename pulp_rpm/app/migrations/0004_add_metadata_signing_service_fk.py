# Generated by Django 2.2.10 on 2020-02-28 18:40

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_rename_last_version'),
        ('rpm', '0003_DATA_incorrect_json'),
    ]

    operations = [
        migrations.AddField(
            model_name='rpmrepository',
            name='metadata_signing_service',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='rpm_rpmrepository', to='core.AsciiArmoredDetachedSigningService'),
        ),
    ]
