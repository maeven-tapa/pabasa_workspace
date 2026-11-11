"""Render synthetic previews of the real live-summary email. No DB or delivery."""
import argparse
import base64
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output' / 'email' / 'live-summary')
    args = parser.parse_args()
    os.environ.update(DJANGO_SETTINGS_MODULE='pabasa_site.settings', DB_ENGINE='sqlite',
        SQLITE_PATH=':memory:', DJANGO_ENV='development', K_SERVICE='', CLOUD_RUN_JOB='')
    sys.path.insert(0, str(ROOT / 'pabasa_site'))
    import django
    django.setup()
    from pabasa_app.live_assessment_email import _logo_bytes, render_summary_email
    from pabasa_app.tests_live_assessment_email import sample_session

    args.output.mkdir(parents=True, exist_ok=True)
    examples = {'one-completed': sample_session(1, 1), 'all-completed': sample_session(5, 5),
                'mixed': sample_session(6, 5), 'maximum-batch': sample_session(10, 7),
                'missing-fields': sample_session(1, 1, missing=True), 'zero-selected': sample_session(0, 0)}
    long_text = sample_session(10, 7)
    long_text[0].section.school.name = 'Illustrative School With a Longer Institutional Name for Layout Validation'
    long_text[0].material.title = 'Illustrative ' + 'Reading Assessment With Long Descriptive Text ' * 3
    long_text[0].teacher.first_name = 'Illustrative Teacher With a Longer Name'
    long_text[1][0].first_name = 'Illustrative Learner With a Longer Recorded Name'
    long_text[1][0].custom_id = 'SAMPLE-LONG-IDENTIFIER-FOR-LAYOUT-CHECKING'
    examples['long-text'] = long_text
    for label, values in examples.items():
        html = render_summary_email(*values)
        # Local previews embed the very same PNG bytes; production uses MIME CID.
        logo = _logo_bytes()
        if logo:
            html = html.replace('cid:pabasa-live-summary-logo',
                                'data:image/png;base64,' + base64.b64encode(logo).decode('ascii'))
        html = html.replace('<title>PABASA Live Assessment Summary</title>',
                            f'<title>ILLUSTRATIVE SAMPLE - {label} - PABASA Live Assessment Summary</title>')
        # The visible banner belongs to the preview only, not the delivered email.
        start = html.index('>', html.index('<body ')) + 1
        html = html[:start] + '<p style="margin:12px;text-align:center;font:12px Arial,sans-serif;color:#496c85;">ILLUSTRATIVE PREVIEW - Fictional student and session data</p>' + html[start:]
        target = args.output / f'{label}.html'
        target.write_text(html, encoding='utf-8')
        print(f'{label}: {target}')


if __name__ == '__main__':
    main()
