"""Jira Cloud API extraction for JTVO."""

from __future__ import annotations

import os
import time
from typing import Any

import pandas as pd
import requests
from atlassian import Jira
from dotenv import load_dotenv

load_dotenv()

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
SP_FIELD = os.getenv("JIRA_STORY_POINTS_FIELD", "customfield_10016")


def _client() -> Jira:
    return Jira(url=JIRA_BASE_URL, username=JIRA_EMAIL, password=JIRA_API_TOKEN)


# ── ADF → Plain Text ───────────────────────────────────────────

def adf_to_text(node: Any) -> str:
    """Recursively convert Atlassian Document Format to plain text."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        children = node.get("content", [])
        parts = [adf_to_text(c) for c in children]
        sep = "\n" if node.get("type") in ("doc", "paragraph", "bulletList",
                                             "orderedList", "listItem",
                                             "blockquote", "codeBlock",
                                             "heading", "table", "tableRow",
                                             "tableCell") else ""
        return sep.join(parts)
    if isinstance(node, list):
        return "\n".join(adf_to_text(c) for c in node)
    return str(node)


# ── Board / Sprint ──────────────────────────────────────────────

def get_boards() -> list[dict]:
    """Return list of Jira boards [{id, name, type}]."""
    jira = _client()
    resp = jira.get_all_agile_boards(board_name=None)
    boards = resp.get("values", []) if isinstance(resp, dict) else resp
    return [{"id": b["id"], "name": b["name"], "type": b.get("type", "")}
            for b in boards]


def get_sprints(board_id: int) -> list[dict]:
    """Return all sprints for a board, newest first."""
    jira = _client()
    sprints: list[dict] = []
    start = 0
    while True:
        resp = jira.get_all_sprint(board_id, start=start, limit=50)
        values = resp.get("values", []) if isinstance(resp, dict) else resp
        if not values:
            break
        for s in values:
            sprints.append({
                "id": s["id"],
                "name": s["name"],
                "state": s.get("state", ""),
                "startDate": s.get("startDate"),
                "endDate": s.get("endDate"),
            })
        if isinstance(resp, dict) and resp.get("isLast", True):
            break
        start += len(values)
    return list(reversed(sprints))


def get_active_sprint(board_id: int) -> dict | None:
    """Return the first active sprint for a board, or None."""
    for s in get_sprints(board_id):
        if s["state"] == "active":
            return s
    return None


def get_sprint_details(sprint_id: int) -> dict:
    """
    Get detailed sprint information including dates.

    Args:
        sprint_id: Jira sprint ID

    Returns:
        Dict with keys: id, name, state, startDate, endDate, completeDate
        Dates are in ISO 8601 format or None if not set
    """
    jira = _client()
    sprint = jira.sprint(sprint_id)
    return {
        "id": sprint["id"],
        "name": sprint["name"],
        "state": sprint.get("state", ""),
        "startDate": sprint.get("startDate"),
        "endDate": sprint.get("endDate"),
        "completeDate": sprint.get("completeDate"),
    }


# ── Issue extraction ────────────────────────────────────────────

def _jql_search(jql: str, fields: str, expand: str = "",
                max_results: int = 50) -> list[dict]:
    """Search issues using the new /rest/api/3/search/jql endpoint."""
    issues: list[dict] = []
    cursor = None
    while True:
        params: dict[str, Any] = {
            "jql": jql,
            "fields": fields,
            "maxResults": max_results,
        }
        if expand:
            params["expand"] = expand
        if cursor:
            params["cursor"] = cursor

        for attempt in range(3):
            resp = requests.get(
                f"{JIRA_BASE_URL}/rest/api/3/search/jql",
                params=params,
                auth=(JIRA_EMAIL, JIRA_API_TOKEN),
            )
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 5))
                time.sleep(wait)
                continue
            resp.raise_for_status()
            break
        else:
            resp.raise_for_status()

        data = resp.json()

        batch = data.get("issues", [])
        if not batch:
            break
        issues.extend(batch)

        next_page = data.get("nextPageToken")
        if not next_page:
            break
        cursor = next_page
        time.sleep(0.5)  # rate limit between pages
    return issues


def _fetch_sprint_issues(sprint_id: int) -> list[dict]:
    """Fetch all issues for a sprint via JQL with changelog expand."""
    fields = (f"summary,status,priority,assignee,resolution,issuetype,"
              f"created,updated,{SP_FIELD},flagged,description,comment")
    return _jql_search(
        jql=f"sprint = {sprint_id}",
        fields=fields,
        expand="changelog",
    )


def _parse_issues(raw_issues: list[dict], board_name: str,
                  sprint_id: int, sprint_name: str) -> pd.DataFrame:
    """Parse raw Jira issues into a DataFrame matching the issues table."""
    rows = []
    for issue in raw_issues:
        f = issue["fields"]
        assignee_obj = f.get("assignee")
        rows.append({
            "key": issue["key"],
            "board_name": board_name,
            "sprint_id": sprint_id,
            "sprint_name": sprint_name,
            "summary": f.get("summary", ""),
            "assignee": assignee_obj["displayName"] if assignee_obj else None,
            "reported_sp": f.get(SP_FIELD) or 0,
            "status": f["status"]["name"] if f.get("status") else "",
            "status_category": (
                f["status"]["statusCategory"]["name"]
                if f.get("status", {}).get("statusCategory") else ""
            ),
            "priority": f["priority"]["name"] if f.get("priority") else "",
            "issuetype": f["issuetype"]["name"] if f.get("issuetype") else "",
            "resolution": f["resolution"]["name"] if f.get("resolution") else None,
            "flagged": bool(f.get("flagged")),
            "created": f.get("created"),
            "updated": f.get("updated"),
            "description": adf_to_text(f.get("description")),
        })
    return pd.DataFrame(rows)


def _parse_comments(raw_issues: list[dict]) -> pd.DataFrame:
    """Extract comments from issues into a DataFrame."""
    rows = []
    for issue in raw_issues:
        comments = (issue["fields"].get("comment", {}) or {}).get("comments", [])
        for c in comments:
            author_obj = c.get("author", {})
            rows.append({
                "id": c["id"],
                "issue_key": issue["key"],
                "author": author_obj.get("displayName", "Unknown"),
                "body": adf_to_text(c.get("body")),
                "created": c.get("created"),
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["id", "issue_key", "author", "body", "created"]
    )


def _parse_changelog(raw_issues: list[dict]) -> pd.DataFrame:
    """Extract changelog entries from issues."""
    rows = []
    for issue in raw_issues:
        changelog = issue.get("changelog", {})
        histories = changelog.get("histories", [])
        for history in histories:
            author_obj = history.get("author", {})
            for item in history.get("items", []):
                item_idx = history.get("items", []).index(item)
                rows.append({
                    "id": f"{issue['key']}_{history['id']}_{item_idx}",
                    "issue_key": issue["key"],
                    "author": author_obj.get("displayName", "Unknown"),
                    "field": item.get("field", ""),
                    "from_string": item.get("fromString"),
                    "to_string": item.get("toString"),
                    "created": history.get("created"),
                })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["id", "issue_key", "author", "field",
                 "from_string", "to_string", "created"]
    )


def extract_sprint_data(
    board_name: str, sprint_id: int, sprint_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """One-shot extraction pipeline.

    Returns (issues_df, comments_df, changelog_df).
    """
    raw = _fetch_sprint_issues(sprint_id)
    issues_df = _parse_issues(raw, board_name, sprint_id, sprint_name)
    comments_df = _parse_comments(raw)
    changelog_df = _parse_changelog(raw)
    return issues_df, comments_df, changelog_df


# ── Future Sprint SP (for sufficiency) ──────────────────────────

def extract_future_sprint_sp(board_id: int) -> float:
    """Sum story points from all future sprints for sufficiency calculation."""
    sprints = get_sprints(board_id)
    future_sprints = [s for s in sprints if s["state"] == "future"]
    total_sp = 0.0
    for sprint in future_sprints:
        time.sleep(1)  # rate limit
        try:
            issues = _jql_search(
                jql=f"sprint = {sprint['id']}",
                fields=SP_FIELD,
                max_results=100,
            )
            for issue in issues:
                sp = issue["fields"].get(SP_FIELD) or 0
                total_sp += float(sp)
        except Exception:
            continue
    return total_sp
