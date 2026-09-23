from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('pabasa_app', '0008_studentactivityrecordingsubmission')]
    operations = [migrations.RunSQL(
        "ALTER TABLE student_activity_recording_submissions ADD COLUMN status varchar(20) NOT NULL DEFAULT 'submitted';",
        "ALTER TABLE student_activity_recording_submissions DROP COLUMN status;",
    ), migrations.RunSQL(
        "ALTER TABLE student_activity_recording_submissions ADD COLUMN checked_at datetime NULL;",
        "ALTER TABLE student_activity_recording_submissions DROP COLUMN checked_at;",
    ), migrations.RunSQL(
        "ALTER TABLE student_activity_recording_submissions ADD COLUMN checked_by_id bigint NULL;",
        "ALTER TABLE student_activity_recording_submissions DROP COLUMN checked_by_id;",
    )]
