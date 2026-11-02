#!/usr/bin/env python3
"""Small, token-safe client for the local Jiuzhou Baimu editing API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class BaimuError(RuntimeError):
    pass


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise BaimuError(f"文件不存在：{path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise BaimuError(f"无法读取 JSON：{path}（{exc}）") from exc


def discover(session_file: Path | None = None) -> tuple[str, str, Path]:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise BaimuError("缺少 LOCALAPPDATA，无法发现百慕安装")

    root = Path(local_app_data) / "MuXuStudio"
    installation_path = root / "installation.json"
    data_dir = root / "data"
    if installation_path.is_file():
        installation = read_json(installation_path)
        configured = installation.get("data") if isinstance(installation, dict) else None
        if configured:
            data_dir = Path(str(configured)).expanduser()

    session_path = data_dir / "session.json"
    if session_file is not None:
        session_path = session_file.expanduser().resolve()
        data_dir = session_path.parent
    if not session_path.is_file():
        raise BaimuError("没有有效的百慕会话；请先启动百慕桌面软件")

    session = read_json(session_path)
    if not isinstance(session, dict) or not isinstance(session.get("url"), str):
        raise BaimuError("百慕 session.json 缺少有效 URL")

    parsed = urllib.parse.urlsplit(session["url"])
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port is None:
        raise BaimuError("拒绝连接非 127.0.0.1 的百慕会话")

    tokens = urllib.parse.parse_qs(parsed.fragment).get("token", [])
    if len(tokens) != 1 or not tokens[0]:
        raise BaimuError("百慕会话缺少临时令牌；请重新启动百慕")

    return f"http://127.0.0.1:{parsed.port}", tokens[0], data_dir


class Client:
    def __init__(self, timeout: float = 30.0, session_file: Path | None = None):
        self.base_url, self._token, self.data_dir = discover(session_file) if session_file is not None else discover()
        self.timeout = timeout

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        body = None
        headers = {
            "Accept": "application/json",
            "X-Studio-Token": self._token,
        }
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                message = json.loads(raw.decode("utf-8")).get("error")
            except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                message = None
            raise BaimuError(message or f"百慕接口返回 HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BaimuError("无法连接百慕；请确认桌面软件正在运行") from exc

        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BaimuError("百慕接口返回了无效 JSON") from exc


def installation_info() -> dict[str, Any]:
    """Report build metadata separately from the running server's identity."""
    local = os.environ.get('LOCALAPPDATA')
    if not local:
        return {}
    path = Path(local) / 'MuXuStudio' / 'installation.json'
    if not path.is_file():
        return {}
    record = read_json(path)
    if not isinstance(record, dict):
        raise BaimuError('安装记录格式无效')
    result = {key: record[key] for key in ('version', 'build_id', 'program', 'data') if key in record}
    if record.get('program'):
        bundle_path = Path(record['program']) / 'bundle.json'
        if bundle_path.is_file():
            bundle = read_json(bundle_path)
            if isinstance(bundle, dict):
                result['installed_bundle'] = {key: bundle[key] for key in ('version', 'build_id') if key in bundle}
    return result


def project_path(project_id: str, suffix: str = "") -> str:
    safe_id = urllib.parse.quote(project_id, safe="")
    return f"/api/projects/{safe_id}{suffix}"


def load_operations(path: Path) -> list[dict[str, Any]]:
    value = read_json(path)
    operations = value.get("operations") if isinstance(value, dict) else value
    if not isinstance(operations, list) or not 1 <= len(operations) <= 100:
        raise BaimuError("编辑文件必须包含 1 至 100 条 operations")
    if not all(isinstance(operation, dict) for operation in operations):
        raise BaimuError("每条编辑操作都必须是 JSON 对象")
    return operations


def current_project(client: Client, project_id: str, revision: int) -> dict[str, Any]:
    project = client.request('GET', project_path(project_id))
    if project.get('revision') != revision:
        raise BaimuError('工程版本已变化，请重新读取并核对')
    return project


def checked_project_write(client: Client, project_id: str, action: str, payload: dict[str, Any]) -> Any:
    saved = client.request('POST', project_path(project_id, '/' + action), payload)
    checked = client.request('GET', project_path(project_id))
    if not isinstance(saved, dict) or saved.get('revision') is None or checked.get('revision') != saved['revision']:
        raise BaimuError('写入后工程再次变化，请重新读取核对；不要重复覆盖')
    return dict(operation=action, project_id=project_id, revision=checked['revision'], project=checked)


def summarize_projects(bootstrap: dict[str, Any]) -> dict[str, Any]:
    summaries = []
    for project in bootstrap.get("projects", []):
        if not isinstance(project, dict):
            continue
        summary = {
            key: project[key]
            for key in ("id", "name", "series", "revision", "archived")
            if key in project
        }
        native = project.get("native")
        if isinstance(native, dict):
            summary["native"] = {
                key: native[key]
                for key in ("shared", "key", "revision", "issues")
                if key in native
            }
        summaries.append(summary)
    return {
        "version": bootstrap.get("version"),
        "data_dir": bootstrap.get("data_dir"),
        "projects": summaries,
        "recovery_issues": bootstrap.get("recovery_issues", []),
    }


def read_subtitle_text(path: Path) -> str:
    if path.suffix.lower() != '.txt':
        raise BaimuError('请选择 TXT 对白文件')
    try:
        if path.stat().st_size > 1024*1024:
            raise BaimuError('TXT 对白不能超过 1 MiB')
        raw = path.read_bytes()
    except OSError as exc:
        raise BaimuError(f'无法读取 TXT：{path}') from exc
    encodings = ['utf-16'] if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else ['utf-8-sig', 'gb18030']
    for encoding in encodings:
        try:
            text = raw.decode(encoding)
        except UnicodeError:
            continue
        if not text.strip() or '\0' in text or '\ufffd' in text:
            raise BaimuError('TXT 为空或编码无效，请另存为 UTF-8 后重试')
        if len(raw) > 1024*1024 or len(text.encode('utf-8')) > 1024*1024:
            raise BaimuError('TXT 对白不能超过 1 MiB')
        return text
    raise BaimuError('无法解码 TXT，请另存为 UTF-8 后重试')


def apply_subtitles(client: Client, project_id: str, revision: int, job_id: str, replace_existing: bool) -> Any:
    project = client.request('GET', project_path(project_id))
    if project.get('revision') != revision:
        raise BaimuError('工程版本已变化，请重新读取并核对')
    if 'caption' in project.get('track_locks', []):
        raise BaimuError('字幕轨道已锁定，未写入字幕')
    job = client.request('GET', '/api/jobs/' + urllib.parse.quote(job_id, safe=''))
    if job.get('project_id') != project_id or job.get('kind') != 'transcribe' or job.get('state') != 'complete':
        raise BaimuError('仅可应用本集已完成的字幕任务；失败或仍排队不代表已生成字幕')
    result = job.get('result', {})
    cues = result.get('captions')
    if not isinstance(cues, list) or not cues:
        raise BaimuError('任务没有有效字幕，不覆盖现有字幕')
    quality = client.request('GET', project_path(project_id, '/quality'))
    if not result.get('sound_digest') or result['sound_digest'] != quality.get('sound_hash'):
        raise BaimuError('音轨或镜头已改变，请按当前最终混音重新做字幕')
    if project.get('captions') == cues:
        return dict(changed=False, project_id=project_id, revision=revision, caption_count=len(cues))
    baseline = job.get('view_reference', {}).get('captions')
    if not isinstance(baseline, list) or baseline != project.get('captions', []):
        raise BaimuError('任务提交后字幕已被编辑，已保留现有字幕；请重新核对并提交任务')
    if project.get('captions') and not replace_existing:
        raise BaimuError('本集已有字幕；只有用户已授权替换时才使用 --replace-existing')
    # A partial project POST preserves every unrelated field and uses the server's
    # atomic revision, lock, native-draft and history checks, including >100 cues.
    saved = client.request('POST', project_path(project_id), dict(revision=revision, captions=cues))
    checked = client.request('GET', project_path(project_id))
    expected = [c.get('text') for c in cues]
    if checked.get('revision') != saved.get('revision') or [c.get('text') for c in checked.get('captions', [])] != expected:
        raise BaimuError('写入后工程再次变化，请重新读取核对；不要重复覆盖')
    return dict(changed=True, project_id=project_id, revision=checked['revision'], caption_count=len(cues),
                alignment=result.get('alignment'), status='字幕已写入工程；仍需试听校对，未导出或交接剪映')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="调用本机九州百慕编辑接口")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument('--session-file', type=Path, help='仅用于用户明确选择的独立试用会话；默认仍连接已安装百慕')
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status")
    subparsers.add_parser("projects")
    subparsers.add_parser('library')
    subparsers.add_parser('fonts')
    subparsers.add_parser('review-skills')

    command = subparsers.add_parser('review-context')
    command.add_argument('project_id')
    command = subparsers.add_parser('review-workflow')
    command.add_argument('project_id')
    command = subparsers.add_parser('review-action')
    command.add_argument('project_id')
    command.add_argument('--request-file', type=Path, required=True)
    command = subparsers.add_parser('confirm-review-rule')
    command.add_argument('project_id')
    command.add_argument('--rules-revision', required=True)
    command.add_argument('--scope-revision', required=True)
    command.add_argument('--rule-id', required=True)
    command.add_argument('--interpretation-file', type=Path, required=True)
    command.add_argument('--confirmed-by-user', action='store_true')

    for name in ("get-project", "native-timeline", "editor-state", "quality", 'history', 'media-status'):
        command = subparsers.add_parser(name)
        command.add_argument("project_id")

    command = subparsers.add_parser('restore')
    command.add_argument('project_id')
    command.add_argument('--revision', type=int, required=True)
    command.add_argument('--history-revision', type=int, required=True)

    for name in ('relink-preview', 'relink-asset'):
        command = subparsers.add_parser(name)
        command.add_argument('project_id')
        command.add_argument('--revision', type=int, required=True)
        command.add_argument('--asset-id', required=True)
        command.add_argument('--path', type=Path, required=True)
        if name == 'relink-asset':
            command.add_argument('--expected-sha256', required=True)
            command.add_argument('--confirmed', action='store_true')

    command = subparsers.add_parser('refresh-assets')
    command.add_argument('project_id')
    command.add_argument('--revision', type=int, required=True)
    command.add_argument('--asset-ids', nargs='+', required=True)
    command.add_argument('--confirmed', action='store_true')

    edit = subparsers.add_parser("apply-edits")
    edit.add_argument("project_id")
    edit.add_argument("--revision", type=int, required=True)
    edit.add_argument("--operations-file", type=Path, required=True)

    handoff = subparsers.add_parser("handoff")
    handoff.add_argument("project_id")
    handoff.add_argument("--revision", type=int, required=True)
    handoff.add_argument("--confirm-jianying-closed", action="store_true")

    export = subparsers.add_parser("batch-export")
    export.add_argument("--request-file", type=Path, required=True)

    job = subparsers.add_parser("job")
    job.add_argument("job_id")

    for name in ('align-subtitles', 'transcribe'):
        command = subparsers.add_parser(name)
        command.add_argument('project_id')
        command.add_argument('--revision', type=int, required=True)
        command.add_argument('--language', default='', help='音频语言；留空自动检测，不沿用工程的旧默认语言')
        if name == 'align-subtitles':
            command.add_argument('--text-file', type=Path, required=True)
            command.add_argument('--split', choices=['lines', 'sentences'], default='lines')
    command = subparsers.add_parser('apply-subtitles')
    command.add_argument('project_id')
    command.add_argument('--revision', type=int, required=True)
    command.add_argument('--job-id', required=True)
    command.add_argument('--replace-existing', action='store_true')
    return parser


def execute(args: argparse.Namespace) -> Any:
    client = Client(args.timeout, args.session_file) if args.session_file is not None else Client(args.timeout)
    if args.command == "status":
        return {
            "identity": client.request("GET", "/api/identity"),
            "health": client.request("GET", "/api/health"),
            "installation": installation_info(),
        }
    if args.command == "projects":
        return summarize_projects(client.request("GET", "/api/bootstrap"))
    if args.command == 'library':
        return client.request('GET', '/api/library')
    if args.command == 'review-skills':
        return client.request('GET', '/api/review-skills')
    if args.command == 'review-context':
        return client.request('GET', project_path(args.project_id, '/review-context'))
    if args.command == 'review-workflow':
        return client.request('GET', project_path(args.project_id, '/review-workflow'))
    if args.command == 'review-action':
        payload = read_json(args.request_file)
        if not isinstance(payload, dict) or payload.get('action') not in ('request_review', 'submit_report', 'repair_progress'):
            raise BaimuError('该命令只提交机审请求、问题单和返工进度；人工标注与固定清单请在百慕界面操作')
        return client.request('POST', project_path(args.project_id, '/review-workflow'), payload)
    if args.command == 'confirm-review-rule':
        if not args.confirmed_by_user:
            raise BaimuError('请先取得用户对规则解释的确认；不能自行确认新增规则')
        try:
            note = args.interpretation_file.read_text(encoding='utf-8-sig')
        except (OSError, UnicodeError) as exc:
            raise BaimuError('无法读取 UTF-8 规则解释文件') from exc
        return client.request('POST', project_path(args.project_id, '/review-confirmation'),
            dict(rules_revision=args.rules_revision, scope_revision=args.scope_revision,
                 id=args.rule_id, interpretation=note, confirmed_by_user=True))
    if args.command == 'fonts':
        bootstrap = client.request('GET', '/api/bootstrap')
        return dict(version=bootstrap.get('version'), fonts=bootstrap.get('fonts', []))
    if args.command == 'history':
        return client.request('GET', project_path(args.project_id, '/history'))
    if args.command == 'media-status':
        return client.request('POST', project_path(args.project_id, '/media-status'), {})
    if args.command == 'restore':
        if args.history_revision < 0:
            raise BaimuError('历史版本必须为非负整数')
        current_project(client, args.project_id, args.revision)
        return checked_project_write(client, args.project_id, 'restore',
            dict(revision=args.revision, history_revision=args.history_revision))
    if args.command in ('relink-preview', 'relink-asset', 'refresh-assets'):
        if args.command != 'relink-preview' and not args.confirmed:
            raise BaimuError('只有用户已授权这次素材重连或刷新时才使用 --confirmed')
        current_project(client, args.project_id, args.revision)
        payload = dict(revision=args.revision)
        if args.command == 'refresh-assets':
            payload.update(asset_ids=args.asset_ids, confirmed=True)
        else:
            payload.update(asset_id=args.asset_id, path=str(args.path.expanduser().resolve()))
            if args.command == 'relink-asset':
                payload.update(expected_sha256=args.expected_sha256, confirmed=True)
        if args.command == 'relink-preview':
            return client.request('POST', project_path(args.project_id, '/relink-preview'), payload)
        return checked_project_write(client, args.project_id, args.command, payload)
    if args.command == "get-project":
        return client.request("GET", project_path(args.project_id))
    if args.command == "native-timeline":
        return client.request("GET", project_path(args.project_id, "/native-timeline"))
    if args.command == "editor-state":
        return client.request("GET", project_path(args.project_id, "/editor-state"))
    if args.command == "quality":
        return client.request("GET", project_path(args.project_id, "/quality"))
    if args.command == "apply-edits":
        operations = load_operations(args.operations_file)
        return client.request(
            "POST",
            project_path(args.project_id, "/edits"),
            {"revision": args.revision, "operations": operations},
        )
    if args.command == "handoff":
        if not args.confirm_jianying_closed:
            raise BaimuError("交接前必须确认用户已保存并离开剪映目标草稿")
        return client.request(
            "POST",
            project_path(args.project_id, "/handoff"),
            {"revision": args.revision},
        )
    if args.command == "batch-export":
        payload = read_json(args.request_file)
        if not isinstance(payload, dict):
            raise BaimuError("批量导出请求必须是 JSON 对象")
        return client.request("POST", "/api/exports/batch", payload)
    if args.command == "job":
        safe_id = urllib.parse.quote(args.job_id, safe="")
        return client.request("GET", f"/api/jobs/{safe_id}")
    if args.command in ('align-subtitles', 'transcribe'):
        project = client.request('GET', project_path(args.project_id))
        if project.get('revision') != args.revision:
            raise BaimuError('工程版本已变化，请重新读取再做字幕')
        if 'caption' in project.get('track_locks', []):
            raise BaimuError('字幕轨道已锁定，请先确认并解锁')
        payload = dict(kind='transcribe', revision=args.revision, language=args.language)
        if args.command == 'align-subtitles':
            payload.update(subtitle_text=read_subtitle_text(args.text_file), subtitle_split=args.split)
        return client.request('POST', project_path(args.project_id, '/jobs'), payload)
    if args.command == 'apply-subtitles':
        return apply_subtitles(client, args.project_id, args.revision, args.job_id, args.replace_existing)
    raise BaimuError("未知命令")


def main() -> int:
    try:
        result = execute(build_parser().parse_args())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except BaimuError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
