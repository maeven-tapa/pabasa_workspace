"""Execute the isolated benchmark using the previously created Cloud Run Job."""

import base64
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SDK = Path(r'C:\Program Files (x86)\Google\Cloud SDK\google-cloud-sdk')
python = SDK / 'platform/bundledpython/python.exe'
gcloud = SDK / 'lib/gcloud.py'
trial = json.loads((ROOT / 'backups/redis-benchmark/trial-connection.json').read_text(encoding='utf-8'))
script = (ROOT / 'tools/benchmark_dashboard_cache.py').read_text(encoding='utf-8')
source = base64.b64encode(script.encode()).decode()
config = base64.b64encode(json.dumps(trial).encode()).decode()
code = f"import sys,base64;sys.argv=['benchmark','{config}'];exec(base64.b64decode('{source}'))"
args = [str(python), str(gcloud), 'run', 'jobs', 'execute', 'pabasa-revision-check-01172',
        '--project=project-2b0d295d-ee06-40a7-927', '--region=asia-southeast1',
        '--args=^~^-c~' + code, '--wait', '--format=value(metadata.name)']
result = subprocess.run(args, capture_output=True, text=True)
if result.returncode:
    # Command errors might echo the arguments containing temporary credentials.
    print(json.dumps({'execution_failed': True, 'exit_code': result.returncode,
                      'details': 'Command output withheld to protect temporary credentials.'}))
else:
    execution = result.stdout.strip()
    (ROOT / 'tmp/redis-benchmark-execution.txt').write_text(execution, encoding='utf-8')
    print(json.dumps({'execution': execution, 'status': 'succeeded'}))
raise SystemExit(result.returncode)
