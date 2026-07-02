#!/usr/bin/env python
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pabasa_site.settings")
django.setup()

from pabasa_app.models import Assessment

# Check 1: Are there assessments without students that have NO attempts?
print("=" * 80)
print("CHECK 1: Parent assessments (source_assessment = NULL, student = NULL)")
print("=" * 80)
parent_assessments = Assessment.objects.filter(source_assessment__isnull=True, student__isnull=True)
print(f"Count: {parent_assessments.count()}")
print(f"These are TEMPLATE/PARENT assessments and should exist BEFORE students attempt them.\n")

# Check 2: Are there attempt rows properly created?
print("=" * 80)
print("CHECK 2: Attempt rows (source_assessment = NOT NULL)")
print("=" * 80)
attempt_rows = Assessment.objects.filter(source_assessment__isnull=False)
print(f"Count: {attempt_rows.count()}")
print(f"These are attempt records linked to parent assessments.\n")

# Check 3: Are there misclassified attempts?
print("=" * 80)
print("CHECK 3: Checking for malformed records")
print("=" * 80)
bad_records = Assessment.objects.filter(source_assessment__isnull=True, student__isnull=False, attempt_number__gt=1)
print(f"Parent assessments with students and attempt_number > 1: {bad_records.count()}")
if bad_records.exists():
    print("These should NOT exist - attempts should be in separate rows with source_assessment set!")
    for b in bad_records[:5]:
        print(f"  - ID={b.id}, code={b.code}, student={b.student.custom_id if b.student else 'None'}, attempt={b.attempt_number}")
else:
    print("GOOD - No malformed records found!\n")

# Check 4: Analyze attempt structure for a sample parent assessment
print("=" * 80)
print("CHECK 4: Sample attempt structure")
print("=" * 80)
sample_parent = parent_assessments.filter(attempt_rows__isnull=False).select_related().first()
if sample_parent:
    attempts = sample_parent.attempt_rows.all()
    print(f"Sample parent: ID={sample_parent.id}, code={sample_parent.code}, title={sample_parent.title}")
    print(f"Number of attempts: {attempts.count()}")
    for attempt in attempts.order_by('attempt_number')[:5]:
        print(f"  - Attempt #{attempt.attempt_number}: student={attempt.student.custom_id}, status={attempt.attempt_status}, completed_at={attempt.completed_at}")
else:
    print("No parent assessment with attempts found yet.")
