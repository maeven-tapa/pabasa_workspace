from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0028_prescribed_reading_audio_features')]
    operations = [migrations.CreateModel(
        name='PrescribedReadingValidationLabel',
        fields=[
            ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('label', models.CharField(choices=[('GREEN', 'Nabasa nang maayos'), ('YELLOW', 'Nabasa pero putol-putol'), ('RED', 'Di nabasa'), ('UNRESOLVED', 'Hindi matukoy')], max_length=12)),
            ('notes', models.TextField(blank=True, default='')),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='validation_labels', to='pabasa_app.prescribedreadingattempt')),
            ('reviewer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='prescribed_reading_validation_labels', to='pabasa_app.user')),
        ],
        options={'db_table': 'prescribed_reading_validation_labels', 'ordering': ['created_at', 'id']},
    ), migrations.AddConstraint(
        model_name='prescribedreadingvalidationlabel',
        constraint=models.UniqueConstraint(fields=('attempt', 'reviewer'), name='unique_prescribed_validation_label'),
    )]
