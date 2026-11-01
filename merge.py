#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step5: 构建 Issue–PR–Commit 关系（保留时间字段，去重 PR 与 commit）
关系优先级：
1. issue↔pr↔commit
2. issue↔commit（排除已在 issue↔pr↔commit 的 commit）
3. pr↔commit（无 issue，排除已在 issue↔pr↔commit 的 PR）
"""
import pandas as pd
import ast
import os

print("🔗 Step 5：正在构建 Issue–PR–Commit 关系...")

# === 1. 读取文件 ===
issues = pd.read_csv("openpilot_issues_with_links.csv", encoding="utf-8-sig")
prs = pd.read_csv("openpilot_prs_bugfix.csv", encoding="utf-8-sig")
pr_commits = pd.read_csv("openpilot_pr_commit_links.csv", encoding="utf-8-sig")

# === 2. 辅助函数 ===
def parse_list(x):
    """解析字符串化列表"""
    if pd.isna(x) or str(x).strip() in ["", "[]"]:
        return []
    try:
        return ast.literal_eval(x) if not isinstance(x, list) else x
    except Exception:
        s = str(x).strip("[]")
        return [i.strip().strip("'\"") for i in s.split(",") if i.strip()]

issues["pr_links"] = issues["pr_links"].apply(parse_list)
issues["commit_links"] = issues["commit_links"].apply(parse_list)

rows = []

# === 3. 构建 issue↔pr↔commit ===
issue_pr_numbers = set()  # 已关联 issue 的 PR
issue_pr_commit_set = set()  # (issue_number, commit_sha) 已被 PR 关联的 commit

for _, issue_row in issues.iterrows():
    issue_num = int(issue_row["number"])
    issue_created = issue_row.get("created_at")
    issue_closed = issue_row.get("closed_at")

    for pr_num_raw in issue_row["pr_links"]:
        try:
            pr_num = int(pr_num_raw)
        except Exception:
            continue

        pr_row = prs[prs["number"] == pr_num]
        pr_created = pr_row.iloc[0]["created_at"] if not pr_row.empty else None
        pr_merged = pr_row.iloc[0]["merged_at"] if not pr_row.empty else None

        linked_commits = []
        if not pr_row.empty and "linked_commits" in pr_row.columns:
            val = pr_row.iloc[0]["linked_commits"]
            try:
                linked_commits = ast.literal_eval(val) if isinstance(val, str) else val
            except Exception:
                linked_commits = []
        if not linked_commits:
            linked_commits = pr_commits[pr_commits["pr_number"] == pr_num]["commit_sha"].tolist()

        for commit_sha in linked_commits:
            rows.append({
                "issue_number": issue_num,
                "pr_number": pr_num,
                "commit_sha": commit_sha,
                "relation_type": "issue↔pr↔commit",
                "issue_created_at": issue_created,
                "issue_closed_at": issue_closed,
                "pr_created_at": pr_created,
                "pr_merged_at": pr_merged
            })
            issue_pr_commit_set.add((issue_num, commit_sha))

        issue_pr_numbers.add(pr_num)

# === 4. 构建 issue↔commit（排除已在 issue↔pr↔commit 的 commit） ===
for _, issue_row in issues.iterrows():
    issue_num = int(issue_row["number"])
    issue_created = issue_row.get("created_at")
    issue_closed = issue_row.get("closed_at")

    for commit in issue_row["commit_links"]:
        if (issue_num, commit) in issue_pr_commit_set:
            continue  # 已在 issue↔pr↔commit 中
        rows.append({
            "issue_number": issue_num,
            "pr_number": None,
            "commit_sha": commit,
            "relation_type": "issue↔commit",
            "issue_created_at": issue_created,
            "issue_closed_at": issue_closed,
            "pr_created_at": None,
            "pr_merged_at": None
        })

# === 5. 构建 pr↔commit（无 issue，排除已在 issue↔pr↔commit 的 PR） ===
for _, prc in pr_commits.iterrows():
    pr_num = int(prc["pr_number"]) if not pd.isna(prc["pr_number"]) else None
    if pr_num in issue_pr_numbers:
        continue  # 已在 issue↔pr↔commit 中
    rows.append({
        "issue_number": None,
        "pr_number": pr_num,
        "commit_sha": prc["commit_sha"],
        "relation_type": "pr↔commit",
        "issue_created_at": None,
        "issue_closed_at": None,
        "pr_created_at": prc.get("pr_created_at", None),
        "pr_merged_at": prc.get("pr_merged_at", None)
    })

# === 6. 输出 ===
relations_df = pd.DataFrame(rows).drop_duplicates()
relations_df.to_csv("openpilot_bug_fix_dataset.csv", index=False, encoding="utf-8-sig")

print(f"✅ Step5 完成：共 {len(relations_df)} 条记录。")
print("📊 关系类型分布：")
print(relations_df["relation_type"].value_counts())
