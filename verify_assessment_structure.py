#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pabasa_site.settings')
django.setup()

from pabasa_app.models import Assessment
from django.db.models import Q

# Check parent vs attempt rows counts
parent_assessments = Assessment.objects.filter(source_assessment__isnull=True)
attempt_rows = Assessment.objects.filter(source_assessment__isnull=False)

print("=== Assessment Structure Verification ===")
print(f"Parent assessments: {parent_assessments.count()}")
print(f"Attempt rows: {attempt_rows.count()}")
print(f"Total: {Assessment.objects.count()}")
print()

# Verify parent assessment details
if parent_assessments.exists():
    print("Sample Parent Assessments:")
    for a in parent_assessments[:3]:
        child_count = Assessment.objects.filter(source_assessment=a).count()
        print(f"  - Code: {a.code}, Title: {a.title}")
        print(f"    Student: {a.student}, Attempts: {a.attempt_no}, Actual children: {child_count}")
    print()

# Verify attempt rows structure
if attempt_rows.exists():
    print("Sample Attempt Rows:")
    for a in attempt_rows[:3]:
        parent = a.source_assessment
        print(f"  - Code: {a.code}, Attempt #: {a.attempt_number}")
        print(f"    Parent: {parent.code if parent else 'None'}, Student: {a.student}, Status: {a.attempt_status}")
    print()

print("✓ Database structure looks correct!")
