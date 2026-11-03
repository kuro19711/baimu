"""GitHub release checks shared by the app and the external skill.

Only public release metadata leaves the machine; no project/session data is used.
The skill distribution copies this module as scripts/baimu_updates.py.
"""
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
import uuid

REPOSITORY = 'https://github.com/kuro19711/baimu'
LATEST = REPOSITORY + '/releases/latest'


def version_key(value):
    match = re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?', str(value))
    if not match:
        raise ValueError('无法比较版本号')
    major, minor, patch, prerelease = match.groups()
    parts = tuple((0, int(p)) if p.isdigit() else (1, p) for p in (prerelease or '').split('.'))
    return (int(major), int(minor), int(patch), prerelease is None, parts)


def github_latest():
    # GitHub's public latest-release redirect avoids unauthenticated API rate limits.
    request = urllib.request.Request(LATEST, method='HEAD', headers={'User-Agent': 'Baimu-Update-Check'})
    with urllib.request.urlopen(request, timeout=8) as response:
        url = urllib.parse.urlsplit(response.geturl())
    prefix = '/kuro19711/baimu/releases/tag/'
    if url.scheme != 'https' or url.netloc != 'github.com' or not url.path.startswith(prefix):
        raise ValueError('GitHub 未返回正式发布版本')
    tag = urllib.parse.unquote(url.path[len(prefix):])
    version_key(tag)
    return {'tag': tag, 'release_url': REPOSITORY + '/releases/tag/' + urllib.parse.quote(tag, safe='')}


@contextmanager
def file_lock(path, timeout=12):
    """OS lock released automatically if a process exits, including crashes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        if stream.seek(0, 2) == 0:
            stream.write(b'0')
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('另一进程正在检查更新')
                time.sleep(0.05)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


class UpdateChecker:
    def __init__(self, root=None, fetch=None, now=None):
        self.root = Path(root) if root is not None else Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local/share'))/'MuXuStudio'/'updates'
        self.fetch = fetch or github_latest
        self.now = now or (lambda: datetime.now().astimezone())

    def _read(self):
        try:
            state = json.loads((self.root/'state.json').read_text(encoding='utf-8'))
            return state if isinstance(state, dict) and state.get('repository') == REPOSITORY else {}
        except (OSError, ValueError):
            return {}

    def _write(self, state):
        temporary = self.root/('state.' + uuid.uuid4().hex + '.tmp')
        try:
            temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temporary, self.root/'state.json')
        finally:
            temporary.unlink(missing_ok=True)

    def check(self, current_version, force=False, claim_notice=False):
        result = {'repository': REPOSITORY, 'current_version': current_version, 'latest_url': LATEST,
                  'update_available': False, 'notify': False}
        try:
            with file_lock(self.root/'check.lock'):
                state = self._read()
                now = self.now()
                today = now.date().isoformat()
                cached = state.get('checked_date') == today and not force
                if not cached:
                    # Persist the attempt before networking: even a killed process does
                    # not make every subsequent conversation repeat today's request.
                    state.update(repository=REPOSITORY, checked_date=today, checked_at=now.isoformat(),
                                 status='interrupted', message='本次检查尚未完成，可手动重试')
                    self._write(state)
                    try:
                        release = self.fetch()
                        version_key(release['tag'])
                        expected = REPOSITORY + '/releases/tag/' + urllib.parse.quote(release['tag'], safe='')
                        if release['release_url'] != expected:
                            raise ValueError('发布地址不匹配')
                        state.update(latest=release, status='ok', message='', success_at=self.now().isoformat())
                    except Exception:
                        state.update(status='error', message='暂时无法检查 GitHub 更新；不影响使用，可点击立即检查重试')
                    self._write(state)
                result.update(status=state.get('status', 'unknown'), checked_at=state.get('checked_at'),
                              checked_date=state.get('checked_date'), cached=cached,
                              message=state.get('message', ''), latest=state.get('latest'),
                              success_at=state.get('success_at'))
                if state.get('status') == 'ok' and isinstance(state.get('latest'), dict):
                    tag = state['latest']['tag']
                    try:
                        result['update_available'] = version_key(tag) > version_key(current_version)
                    except ValueError:
                        result['message'] = '已取得 GitHub 版本，本机版本格式未知，请对照发布说明'
                    if result['update_available'] and claim_notice and state.get('notified_tag') != tag:
                        state['notified_tag'] = tag
                        self._write(state)
                        result['notify'] = True
        except (OSError, TimeoutError, ValueError, KeyError, TypeError):
            result.update(status='unavailable', message='更新检查暂不可用，不影响使用')
        return result
