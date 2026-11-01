#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Step 1:
抓取 commaai/openpilot 从 2022-11-16 起的 Issues / Pull Requests。
输出：openpilot_issues_prs.csv
"""

import os
from datetime import datetime, timezone
import pandas as pd
from github import Github, Auth
from dotenv import load_dotenv
from tqdm import tqdm

# === 初始化 ===
load_dotenv()
auth = Auth.Token(os.getenv("GITHUB_TOKEN"))
g = Github(auth=auth)
repo = g.get_repo("commaai/openpilot")

CUTOFF_DATE = datetime(2022, 11, 16, tzinfo=timezone.utc)
os.makedirs("data", exist_ok=True)

print(f"📥 抓取 openpilot Issues / PRs (仅 {CUTOFF_DATE.date()} 之后)...")

issues = repo.get_issues(state="all", sort="created", direction="desc")
records = []

for issue in tqdm(issues, desc="Scanning Issues/PRs"):
    if issue.created_at < CUTOFF_DATE:
        print(f"⏹️ 到达截止时间 {CUTOFF_DATE.date()}，停止。")
        break

    is_pr = issue.pull_request is not None
    merged = False
    merged_at = None

    if is_pr:
        try:
            pr = issue.as_pull_request()
            merged = pr.merged
            merged_at = pr.merged_at
        except Exception:
            pass

    labels = ";".join([l.name for l in issue.labels]) if issue.labels else ""
    comments = []
    try:
        for c in issue.get_comments():
            if c.body:
                comments.append(c.body.replace("\n", " "))
    except Exception:
        pass

    records.append({
        "id": issue.id,
        "number": issue.number,
        "title": issue.title,
        "is_pull_request": is_pr,
        "merged": merged,
        "merged_at": merged_at,
        "state": issue.state,
        "labels": labels,
        "description": issue.body.replace("\n", " ") if issue.body else "",
        "comments": " || ".join(comments),
        "comments_count": issue.comments,
        "created_at": issue.created_at,
        "closed_at": issue.closed_at,
    })

df = pd.DataFrame(records)
df.to_csv("openpilot_issues_prs.csv", index=False, encoding="utf-8-sig")
print(f"✅ Step 1 完成，共 {len(df)} 条记录。")
