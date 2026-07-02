#!/usr/bin/env python
"""Comprehensive diagnostic for assessment and attempt row structure."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pabasa_site.settings")
django.setup()

from pabasa_app.models import Assessment
from django.db.models import Q, Count

print("\n" + "="*100)
print("COMPREHENSIVE ASSESSMENT DIAGNOSTIC")
print("="*100 + "\n")

# Statistics
total_assessments = Assessment.objects.count()
parent_assessments = Assessment.objects.filter(source_assessment__isnull=True).count()
attempt_rows = Assessment.objects.filter(source_assessment__isnull=False).count()

print(f"Total Assessment records: {total_assessments}")
print(f"  - Parent assessments (source_assessment=NULL): {parent_assessments}")
print(f"  - Attempt rows (source_assessment!=NULL): {attempt_rows}\n")

# Issue 1: Check if parent assessments exist before any students attempt them
print("="*100)
print("ISSUE 1: Empty Parent Assessments (no attempts yet)")
print("="*100)
empty_parents = Assessment.objects.filter(
    source_assessment__isnull=True,  # Is a parent
    attempt_rows__isnull=True  # Has no attempt rows
)
print(f"Count: {empty_parents.count()}")
if empty_parents.count() > 0:
    print("These are NORMAL - parents exist before students attempt them.")
    print("This is expected behavior.\n")
else:
    print("All parent assessments have at least one attempt row.\n")

# Issue 2: Check if attempts are being recorded correctly as separate rows
print("="*100)
print("ISSUE 2: Attempts Storage (should be separate rows)")
print("="*100)

# Find parent assessments that should have multiple attempts
parents_with_attempts = Assessment.objects.filter(
    source_assessment__isnull=True
).annotate(attempt_count=Count('attempt_rows')).filter(attempt_count__gt=0)

print(f"Parent assessments with attempts: {parents_with_attempts.count()}\n")

# Sample check: look for attempt rows
if parents_with_attempts.exists():
    sample_parent = parents_with_attempts.first()
    attempts = sample_parent.attempt_rows.all().order_by('attempt_number', 'created_at')
    print(f"Sample parent: ID={sample_parent.id}, code={sample_parent.code}")
    print(f"Title: {sample_parent.title}")
    print(f"Total attempts stored: {attempts.count()}\n")
    
    print("Attempt rows detail:")
    print(f"{'Attempt#':<10} {'StudentID':<10} {'Status':<12} {'Created':<30}")
    print("-" * 65)
    for att in attempts[:10]:
        print(f"{att.attempt_number:<10} {att.student_id:<10} {att.attempt_status:<12} {att.created_at.isoformat():<30}")
    
    if attempts.count() > 10:
        print(f"... and {attempts.count() - 10} more attempts")

print("\n")

# Issue 3: Check for misclassified attempts (parent with student AND high attempt_number)
print("="*100)
print("ISSUE 3: Malformed Records (attempt data on parent rows)")
print("="*100)

malformed = Assessment.objects.filter(
    source_assessment__isnull=True,  # Is a parent
    student__isnull=False  # Has a student (BAD - should be NULL)
)
print(f"Count: {malformed.count()}")
if malformed.count() > 0:
    print("ERROR - Found parent assessments with students!")
    print("These should NOT have student_id set!\n")
    for m in malformed[:5]:
        print(f"  - ID={m.id}, code={m.code}, student={m.student.custom_id}, attempt_number={m.attempt_number}")
else:
    print("GOOD - No malformed records found (no parents with students).\n")

# Issue 4: Check if multiple attempts on same row are being recorded
print("="*100)
print("ISSUE 4: Check for Duplicate Attempt Updates (bugs in recording)")
print("="*100)

# Look for attempt rows from the same student on the same parent with recent timestamps
from django.utils import timezone
from datetime import timedelta

# Get all attempt rows
all_attempts = Assessment.objects.filter(source_assessment__isnull=False)

# Group by parent_id and student_id to see attempts per student
attempt_groups = {}
for attempt in all_attempts:
    key = (attempt.source_assessment_id, attempt.student_id)
    if key not in attempt_groups:
        attempt_groups[key] = []
    attempt_groups[key].append(attempt)

# Check if all attempt_numbers are sequential and unique per student
issues_found = False
for (parent_id, student_id), attempts_list in attempt_groups.items():
    if len(attempts_list) < 2:
        continue
    
    attempt_numbers = sorted([a.attempt_number for a in attempts_list])
    expected_numbers = list(range(1, len(attempts_list) + 1))
    
    if attempt_numbers != expected_numbers:
        if not issues_found:
            print("ERROR - Found non-sequential attempt numbers!\n")
            issues_found = True
        
        parent = Assessment.objects.get(id=parent_id)
        student = Assessment.objects.get(id=attempts_list[0].student_id).student
        print(f"Parent: {parent.code}")
        print(f"Student: {student.custom_id if student else 'Unknown'}")
        print(f"Expected attempt numbers: {expected_numbers}")
        print(f"Actual attempt numbers: {attempt_numbers}\n")

if not issues_found:
    print("GOOD - All attempt numbers are sequential and correct.\n")

# Summary
print("="*100)
print("SUMMARY")
print("="*100)
print(f"Parent assessments: {parent_assessments}")
print(f"Attempt rows: {attempt_rows}")
print(f"Expected: attempt rows should be in separate Assessment records with source_assessment_id set")
print(f"Status: {'VERIFIED CORRECT' if malformed.count() == 0 else 'ISSUES FOUND'}")
