#!/usr/bin/env python3
"""Send GitHub Issue and pull request changes to an official QQ group bot."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


TOKEN_URL = "https://bots.qq.com/app/getAppAccessToken"
API_BASE_URL = "https://api.bot.qq.com"
TRANSIENT_HTTP_STATUSES = {429, 500, 502, 503, 504}
URL_REJECTED_CODE = 40054010
URL_PATTERN = re.compile(r"(?i)\b(?:https?://|www\.)\S+")

ISSUE_ACTIONS = {
    "opened": "已打开",
    "edited": "已编辑",
    "deleted": "已删除",
    "transferred": "已转移",
    "pinned": "已置顶",
    "unpinned": "已取消置顶",
    "closed": "已关闭",
    "reopened": "已重新打开",
    "assigned": "已指派",
    "unassigned": "已取消指派",
    "labeled": "已添加标签",
    "unlabeled": "已移除标签",
    "locked": "已锁定讨论",
    "unlocked": "已解锁讨论",
    "milestoned": "已加入里程碑",
    "demilestoned": "已移出里程碑",
}

PULL_REQUEST_ACTIONS = {
    "assigned": "已指派",
    "unassigned": "已取消指派",
    "labeled": "已添加标签",
    "unlabeled": "已移除标签",
    "opened": "已打开",
    "edited": "已编辑",
    "closed": "已关闭",
    "reopened": "已重新打开",
    "synchronize": "提交已更新",
    "converted_to_draft": "已转为草稿",
    "locked": "已锁定讨论",
    "unlocked": "已解锁讨论",
    "enqueued": "已进入合并队列",
    "dequeued": "已退出合并队列",
    "milestoned": "已加入里程碑",
    "demilestoned": "已移出里程碑",
    "ready_for_review": "已可供评审",
    "review_requested": "已请求评审",
    "review_request_removed": "已取消评审请求",
    "auto_merge_enabled": "已启用自动合并",
    "auto_merge_disabled": "已禁用自动合并",
}


class ConfigurationError(RuntimeError):
    """Raised when a required GitHub Actions secret is missing."""


@dataclass
class QQAPIError(RuntimeError):
    status: int
    code: int | None
    message: str

    def __str__(self) -> str:
        code = f", QQ code {self.code}" if self.code is not None else ""
        return f"QQ API request failed (HTTP {self.status}{code}): {self.message}"


def _clean_text(value: Any, max_length: int) -> str:
    text = str(value or "")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def _login(value: Any) -> str:
    if isinstance(value, Mapping):
        return _clean_text(value.get("login"), 80)
    return ""


def _join_message_lines(lines: list[str], max_length: int = 900) -> str:
    message = "\n".join(line for line in lines if line)
    if len(message) <= max_length:
        return message
    return message[: max_length - 1].rstrip() + "…"


def _remove_urls(value: str) -> str:
    return URL_PATTERN.sub("[链接已省略]", value)


def _event_detail(event_name: str, action: str, payload: Mapping[str, Any]) -> str:
    if action in {"labeled", "unlabeled"}:
        label = payload.get("label") or {}
        return f"标签：{_clean_text(label.get('name'), 80)}"
    if action in {"assigned", "unassigned"}:
        return f"处理人：{_login(payload.get('assignee'))}"
    if action in {"milestoned", "demilestoned"}:
        milestone = payload.get("milestone") or {}
        return f"里程碑：{_clean_text(milestone.get('title'), 100)}"
    if action in {"review_requested", "review_request_removed"}:
        reviewer = _login(payload.get("requested_reviewer"))
        team = payload.get("requested_team") or {}
        target = reviewer or _clean_text(team.get("name"), 80)
        return f"评审人：{target}"
    if event_name == "pull_request_target" and action == "synchronize":
        before = _clean_text(payload.get("before"), 12)
        after = _clean_text(payload.get("after"), 12)
        if before and after:
            return f"提交：{before[:7]} -> {after[:7]}"
    return ""


def build_notification(
    event_name: str,
    payload: Mapping[str, Any],
    repository: str,
    actor: str,
    run_url: str,
    *,
    include_url: bool,
) -> str:
    """Build a bounded plain-text notification from a GitHub event payload."""
    action = _clean_text(payload.get("action"), 60)
    repository_name = _clean_text(repository.rsplit("/", 1)[-1], 80) or "GitHub"
    prefix = f"[{repository_name} GitHub]"

    if event_name == "workflow_dispatch":
        inputs = payload.get("inputs") or {}
        lines = [
            f"{prefix} QQ 群通知测试",
            f"内容：{_clean_text(inputs.get('message'), 240)}",
            f"操作者：{_clean_text(actor, 80)}",
        ]
        if include_url and run_url:
            lines.append(f"运行：{run_url}")
        message = _join_message_lines(lines)
        return message if include_url else _remove_urls(message)

    if event_name == "issues":
        item = payload.get("issue") or {}
        item_name = "Issue"
        action_label = ISSUE_ACTIONS.get(action, f"状态已变更（{action}）")
    elif event_name == "pull_request_target":
        item = payload.get("pull_request") or {}
        item_name = "PR"
        if action == "closed" and item.get("merged"):
            action_label = "已合并"
        else:
            action_label = PULL_REQUEST_ACTIONS.get(action, f"状态已变更（{action}）")
    else:
        raise ValueError(f"Unsupported GitHub event: {event_name}")

    number = item.get("number") or payload.get("number") or "?"
    title = _clean_text(item.get("title"), 220)
    sender = _login(payload.get("sender")) or _clean_text(actor, 80)
    detail = _event_detail(event_name, action, payload)
    html_url = _clean_text(item.get("html_url"), 500)

    lines = [
        f"{prefix} {item_name} #{number} {action_label}",
        f"标题：{title}",
        f"操作者：{sender}",
    ]
    if detail and not detail.endswith("："):
        lines.append(detail)
    if include_url and html_url:
        lines.append(f"链接：{html_url}")

    message = _join_message_lines(lines)
    return message if include_url else _remove_urls(message)


def _decode_api_error(status: int, body: bytes) -> QQAPIError:
    message = body.decode("utf-8", errors="replace")[:500]
    code: int | None = None
    try:
        data = json.loads(message)
        if isinstance(data, Mapping):
            raw_code = data.get("code")
            code = int(raw_code) if raw_code is not None else None
            message = str(data.get("message") or data.get("msg") or message)
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    return QQAPIError(status=status, code=code, message=_clean_text(message, 300))


def _post_json(url: str, payload: Mapping[str, Any], headers: Mapping[str, str]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **headers}

    for attempt in range(3):
        request = Request(url, data=body, headers=request_headers, method="POST")
        try:
            with urlopen(request, timeout=15) as response:
                response_body = response.read()
                return json.loads(response_body.decode("utf-8")) if response_body else {}
        except HTTPError as error:
            api_error = _decode_api_error(error.code, error.read())
            if error.code not in TRANSIENT_HTTP_STATUSES or attempt == 2:
                raise api_error from error
        except URLError as error:
            if attempt == 2:
                raise RuntimeError(f"QQ API network request failed: {error.reason}") from error
        time.sleep(2**attempt)

    raise AssertionError("unreachable")


def get_access_token(app_id: str, client_secret: str) -> str:
    response = _post_json(
        TOKEN_URL,
        {"appId": app_id, "clientSecret": client_secret},
        {},
    )
    token = response.get("access_token")
    if not token:
        raise RuntimeError("QQ access-token response did not contain access_token")
    return str(token)


def send_group_message(group_openid: str, access_token: str, content: str) -> dict[str, Any]:
    encoded_group = quote(group_openid, safe="")
    return _post_json(
        f"{API_BASE_URL}/v2/groups/{encoded_group}/messages",
        {"msg_type": 0, "content": content},
        {"Authorization": f"QQBot {access_token}"},
    )


def send_with_url_fallback(
    group_openid: str,
    access_token: str,
    content_with_url: str,
    content_without_url: str,
) -> tuple[dict[str, Any], bool]:
    """Retry without the GitHub URL when the bot has no URL permission."""
    try:
        return send_group_message(group_openid, access_token, content_with_url), False
    except QQAPIError as error:
        if error.code != URL_REJECTED_CODE or content_with_url == content_without_url:
            raise
    return send_group_message(group_openid, access_token, content_without_url), True


def _required_environment() -> tuple[str, str, str]:
    names = ("QQ_BOT_APP_ID", "QQ_BOT_CLIENT_SECRET", "QQ_GROUP_OPENID")
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise ConfigurationError("Missing required GitHub Actions secrets: " + ", ".join(missing))
    return tuple(os.environ[name] for name in names)  # type: ignore[return-value]


def _is_true(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    event_path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    if not event_path.is_file():
        raise ConfigurationError("GITHUB_EVENT_PATH does not point to an event payload")

    with event_path.open(encoding="utf-8") as event_file:
        payload = json.load(event_file)

    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "OtterMind/Chat2DB")
    actor = os.environ.get("GITHUB_ACTOR", "unknown")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_url = f"{server_url}/{repository}/actions/runs/{run_id}" if run_id else ""
    include_url = _is_true(os.environ.get("QQ_INCLUDE_URL", "true"))

    message_with_url = build_notification(
        event_name, payload, repository, actor, run_url, include_url=include_url
    )
    message_without_url = build_notification(
        event_name, payload, repository, actor, run_url, include_url=False
    )

    action = _clean_text(payload.get("action") or "manual", 60)
    if _is_true(os.environ.get("QQ_DRY_RUN")):
        print(f"QQ notification dry run passed: event={event_name}, action={action}")
        return 0

    app_id, client_secret, group_openid = _required_environment()
    token = get_access_token(app_id, client_secret)
    response, removed_url = send_with_url_fallback(
        group_openid, token, message_with_url, message_without_url
    )
    message_id = _clean_text(response.get("id"), 160)
    suffix = "; URL removed by fallback" if removed_url else ""
    print(f"QQ notification sent: message_id={message_id or 'unknown'}{suffix}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ConfigurationError, QQAPIError, RuntimeError, ValueError) as error:
        print(f"QQ notification failed: {error}", file=sys.stderr)
        sys.exit(1)
