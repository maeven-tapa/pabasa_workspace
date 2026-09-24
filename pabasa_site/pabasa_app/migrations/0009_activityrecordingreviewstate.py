from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0008_studentactivityrecordingsubmission')]
    # 0008 already creates the complete StudentActivityRecordingSubmission
    # schema, including status, checked_at, and checked_by_id.  This migration
    # remains as the historical migration name but must not add those columns
    # a second time on SQLite (or any other database).
    operations = []
