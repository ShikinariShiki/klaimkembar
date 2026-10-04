"""One-command local launcher: python run.py. Requires Python >=3.13."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if sys.version_info < (3, 13):
    raise SystemExit('Gunakan Python 3.13 atau lebih baru.')
python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
if not python.exists():
    subprocess.run([sys.executable, '-m', 'venv', '.venv'], check=True)
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
if not Path('.env').exists():
    subprocess.run([str(python), '-m', 'scripts.manage', 'init-env'], check=True)
subprocess.run([str(python), '-c', "from dotenv import load_dotenv; import runpy; load_dotenv(); runpy.run_module('scripts.manage', run_name='__main__')", 'migrate'], check=True)
environment = dict(os.environ, LOCAL_UI='true')
print('KlaimKembar: http://127.0.0.1:8000 | data sintetis saja | Ctrl+C untuk berhenti', flush=True)
try:
    subprocess.run([str(python), '-m', 'uvicorn', 'klaimkembar.main:app', '--env-file', '.env', '--host', '127.0.0.1', '--port', '8000', '--no-access-log'], env=environment, check=True)
except KeyboardInterrupt:
    pass
