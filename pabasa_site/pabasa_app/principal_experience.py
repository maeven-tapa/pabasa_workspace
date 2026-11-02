"""Presentation helpers only; monitoring calculations stay in principal_reporting."""
from .principal_reporting import percent


def learning_context(snapshot):
    snapshot['official_tasks'] = [r for r in snapshot['assessment_rows'] if r['is_official']]
    snapshot['other_tasks'] = [r for r in snapshot['assessment_rows'] if not r['is_official']]
    snapshot['missing_percentage'] = percent(snapshot['missing_official_students'], snapshot['total_students'])
    snapshot['unassigned_sections'] = sum(r['teacher'] == 'Unassigned' for r in snapshot['section_rows'])
    snapshot['follow_up_count'] = len(snapshot.get('follow_up_rows', []))
    snapshot['intervention_follow_up_count'] = sum(r['reason'] != 'Official CRLA result missing' for r in snapshot.get('follow_up_rows', []))
    snapshot['section_count_label'] = 'Active sections' if not snapshot['scope_calendar'] or snapshot['scope_calendar'].is_active else 'Sections in selected year'
    return snapshot
