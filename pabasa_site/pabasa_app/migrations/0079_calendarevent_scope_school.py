from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0078_user_must_change_password")]

    operations = [
        migrations.AddField(
            model_name="calendarevent",
            name="scope",
            field=models.CharField(
                choices=[("global", "Global"), ("school", "School-local")],
                default="global",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="calendarevent",
            name="school",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="calendar_events",
                to="pabasa_app.school",
            ),
        ),
        migrations.AddConstraint(
            model_name="calendarevent",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(scope="global", school__isnull=True)
                    | models.Q(scope="school", school__isnull=False)
                ),
                name="calendar_event_scope_school_consistent",
            ),
        ),
    ]
