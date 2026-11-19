"""Support bundle: one ZIP of non-sensitive diagnostics for troubleshooting (docs/support-bundle.md).

Contains build/runtime information, recent logs (redacted), sanitized settings, capability states,
connection and telemetry counters. Never contains report contents, photos, credentials or the
vessel's position history.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import sys
import tempfile
import zipfile

SECRET_KEY = re.compile(r'(pass(word)?|secret|token|api[_-]?key|credential|auth|cookie|session)', re.I)
SECRET_TEXT = [
    # "Authorization: Bearer <token>" — the scheme word must not shield the token itself.
    (re.compile(r'(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|apikey|authorization)\b\s*[:=]\s*(?:(?:bearer|basic|token)\s+)?\S+'), r'\1=[redacted]'),
    (re.compile(r'(?i)\bbearer\s+[a-z0-9._\-~+/=]+'), 'Bearer [redacted]'),
    (re.compile(r'(?i)(https?://[^\s?]+)\?[^\s]+'), r'\1?[redacted]'),
]
POSITION_KEY = re.compile(r'(^|[_\-\s])(lat|lon|latitude|longitude|position|track|coords?|coordinates)($|[_\-\s])', re.I)
MAX_LOG_BYTES = 512 * 1024


def redact_text(text):
    for pattern, replacement in SECRET_TEXT:
        text = pattern.sub(replacement, text)
    home = str(Path.home())
    return text.replace(home, '%USERPROFILE%').replace(home.replace('\\', '/'), '%USERPROFILE%')


def sanitize_settings(values):
    """Settings dict -> copy with secrets and position-like values redacted."""
    result = {}
    for key, value in sorted(values.items()):
        if SECRET_KEY.search(key):
            result[key] = '[redacted]'
        elif POSITION_KEY.search(key.split('/')[-1]):
            result[key] = '[omitted: position]'
        else:
            result[key] = redact_text(str(value))
    return result


def runtime_info():
    from app.version import STAGE, __version__, edition
    from app.qt import API
    try:
        from app.qt.QtCore import qVersion
        qt = qVersion()
    except Exception:  # pragma: no cover
        qt = 'unknown'
    info = dict(version=__version__, stage=STAGE, edition=edition(), commit=build_commit(), python=platform.python_version(),
                qt_binding=API, qt_version=qt, os=platform.platform(), architecture=platform.machine() or platform.architecture()[0],
                frozen=bool(getattr(sys, 'frozen', False)), build_info=build_info_text())
    return info


def build_info_text():
    """BUILD_INFO.txt written by the PyInstaller specs (packaged builds only)."""
    base = Path(getattr(sys, '_MEIPASS', '')) if getattr(sys, 'frozen', False) else None
    for candidate in ([base/'BUILD_INFO.txt', Path(sys.executable).parent/'BUILD_INFO.txt'] if base else []):
        if candidate.exists():
            return candidate.read_text(encoding='utf-8', errors='replace').strip()
    return ''


def build_commit():
    text = build_info_text()
    match = re.search(r'Commit:\s*(\S+)', text)
    if match:
        return match.group(1)
    try:
        import subprocess
        root = Path(__file__).resolve().parents[2]
        sha = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=str(root), capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=str(root), capture_output=True, text=True, timeout=5).stdout.strip()
        return (sha + ('+uncommitted' if dirty else '')) if sha else 'unknown'
    except Exception:
        return 'unknown'


def log_dir():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home())))/'GDS VTS'/'logs'


def write_bundle(destination, settings=None, diagnostics=None, logs=None):
    """Write the ZIP atomically. ``settings`` is a plain dict of QSettings values, ``diagnostics`` a
    dict of live app state (connection/telemetry counters). Returns (path, list of member names)."""
    destination = Path(destination)
    members = {}
    created = datetime.now(timezone.utc).isoformat(timespec='seconds')
    members['README.txt'] = ('GDS VTS support bundle\n'
        f'Created: {created}\n\n'
        'Contains diagnostics only: build/runtime information, recent application logs (redacted),\n'
        'sanitized settings, capability states and connection/telemetry counters.\n'
        'Does NOT contain report contents, photos, passwords, API keys, tokens or vessel position history.\n')
    members['build_and_runtime.json'] = json.dumps(runtime_info(), indent=2)
    members['settings_sanitized.json'] = json.dumps(sanitize_settings(settings or {}), indent=2)
    members['diagnostics.json'] = json.dumps(redact_diagnostics(diagnostics or {}), indent=2, default=str)
    for path in (logs if logs is not None else sorted(log_dir().glob('*.log'))):
        path = Path(path)
        try:
            raw = path.read_bytes()[-MAX_LOG_BYTES:]
            members['logs/' + path.name] = redact_text(raw.decode('utf-8', errors='replace'))
        except OSError:
            continue
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.gds-support-', suffix='.zip', dir=str(destination.parent))
    os.close(fd)
    try:
        with zipfile.ZipFile(temp, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, text in members.items():
                archive.writestr(name, text)
        os.replace(temp, str(destination))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return destination, sorted(members)


def redact_diagnostics(values):
    """Drop position-like keys and redact secrets anywhere in nested diagnostics."""
    if isinstance(values, dict):
        return {k: ('[omitted: position]' if POSITION_KEY.search(str(k)) else '[redacted]' if SECRET_KEY.search(str(k)) else redact_diagnostics(v))
                for k, v in values.items()}
    if isinstance(values, (list, tuple)):
        return [redact_diagnostics(v) for v in values]
    if isinstance(values, str):
        return redact_text(values)
    return values


def suggested_name():
    return f'GDS-VTS-support-{datetime.now():%Y%m%d-%H%M%S}.zip'
