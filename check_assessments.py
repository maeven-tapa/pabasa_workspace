#!/usr/bin/env python
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pabasa_site.settings")
django.setup()

from pabasa_app.models import Assessment

# Get all assessments
assessments = Assessment.objects.all().order_by('-created_at')[:30]
print(f'Total assessments in database: {Assessment.objects.count()}\n')

# Categorize assessments
parent_assessments = [a for a in assessments if a.source_assessment_id is None]
attempt_rows = [a for a in assessments if a.source_assessment_id is not None]

print(f"Parent assessments (source_assessment is NULL): {len(parent_assessments)}")
print(f"Attempt rows (source_assessment is NOT NULL): {len(attempt_rows)}\n")

print(f"{'ID':<6} {'Code':<20} {'Title':<30} {'Type':<10} {'Source':<8} {'Student':<15} {'Attempt':<8} {'Status':<12}")
print('-' * 130)

for a in assessments:
    source_id = a.source_assessment_id if a.source_assessment_id else 'PARENT'
    student_name = f'{a.student.custom_id}' if a.student else 'None'
    attempt = a.attempt_number if a.attempt_number else 'N/A'
    print(f'{a.id:<6} {a.code:<20} {(a.title[:28]):<30} {a.assessment_type:<10} {str(source_id):<8} {student_name:<15} {str(attempt):<8} {a.attempt_status:<12}')

print(f"\n\nChecking for empty/no-student parent assessments:")
empty_parents = Assessment.objects.filter(source_assessment__isnull=True, student__isnull=True)
print(f"Parent assessments with no student (should exist for templates): {empty_parents.count()}")

print(f"\nChecking for duplicate attempts on single row:")
# Find assessments that have multiple attempts recorded on single row
multi_attempt_rows = Assessment.objects.filter(source_assessment__isnull=True, student__isnull=False).exclude(attempt_number=1)
print(f"Attempts recorded on parent assessment (instead of as separate rows): {multi_attempt_rows.count()}")
if multi_attempt_rows.exists():
    for a in multi_attempt_rows[:5]:
        print(f"  - {a.code}: attempt #{a.attempt_number}, student={a.student.custom_id}, source_assessment={a.source_assessment_id}")
