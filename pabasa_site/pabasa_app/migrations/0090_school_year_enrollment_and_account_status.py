from django.db import migrations, models
import django.db.models.deletion

def backfill_school_year_enrollments(apps, schema_editor):
    User = apps.get_model("pabasa_app", "User")
    Enrollment = apps.get_model("pabasa_app", "Enrollment")
    User.objects.filter(is_archived=True).update(account_status="archived")
    User.objects.filter(is_archived=False).update(account_status="active")
    for enrollment in Enrollment.objects.select_related("section").all().iterator():
        section = enrollment.section
        Enrollment.objects.filter(pk=enrollment.pk).update(
            school_id=section.school_id, school_calendar_id=section.school_calendar_id,
            grade_level=section.grade_level or "Grade 2",
            assigned_teacher_id=section.teacher_id,
            status="active" if enrollment.is_active else "completed",
            outcome="not_finalized",
        )

class Migration(migrations.Migration):
    dependencies = [("pabasa_app", "0089_school_calendar_section_and_user")]
    operations = [
        migrations.AddField(model_name="user", name="account_status", field=models.CharField(choices=[("active", "Active"), ("pending_archive", "Pending Archive"), ("archived", "Archived")], default="active", max_length=20)),
        migrations.AlterField(model_name="enrollment", name="section", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="enrollments", to="pabasa_app.section")),
        migrations.AddField(model_name="enrollment", name="school", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="pabasa_app.school")),
        migrations.AddField(model_name="enrollment", name="school_calendar", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="enrollments", to="pabasa_app.schoolcalendar")),
        migrations.AddField(model_name="enrollment", name="grade_level", field=models.CharField(blank=True, default="Grade 2", max_length=20)),
        migrations.AddField(model_name="enrollment", name="assigned_teacher", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_enrollments", to="pabasa_app.user")),
        migrations.AddField(model_name="enrollment", name="status", field=models.CharField(choices=[("active", "Active"), ("completed", "Completed"), ("awaiting_assignment", "Awaiting Assignment")], default="active", max_length=30)),
        migrations.AddField(model_name="enrollment", name="outcome", field=models.CharField(choices=[("not_finalized", "Not Finalized"), ("promoted", "Promoted"), ("retained", "Retained")], default="not_finalized", max_length=20)),
        migrations.AddField(model_name="enrollment", name="finalized_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="finalized_enrollments", to="pabasa_app.user")),
        migrations.AddField(model_name="enrollment", name="finalized_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="enrollment", name="updated_at", field=models.DateTimeField(auto_now=True)),
        migrations.CreateModel(name="AccountStatusHistory", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("status", models.CharField(choices=[("active", "Active"), ("pending_archive", "Pending Archive"), ("archived", "Archived")], max_length=20)),
            ("reason", models.CharField(blank=True, max_length=255)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("changed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="account_status_changes", to="pabasa_app.user")),
            ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="account_status_history", to="pabasa_app.user")),
        ], options={"ordering": ["-created_at", "-id"]}),
        migrations.RunPython(backfill_school_year_enrollments, migrations.RunPython.noop),
    ]
