import re
import pandas as pd
from github import Github, Auth
from dotenv import load_dotenv
from tqdm import tqdm
import os

load_dotenv()
auth = Auth.Token(os.getenv("GITHUB_TOKEN"))
g = Github(auth=auth)
repo = g.get_repo("commaai/openpilot")

df = pd.read_csv("openpilot_issues_prs.csv", encoding="utf-8-sig")

# 只保留 PR 且 merged_at 非空（你原先逻辑）
df_pr = df[(df["is_pull_request"]) & (df["merged_at"].notna())]

# 修复关键词（可按需调整）
fix_keywords = [
    # 动词类
    "fix", "fixed", "fixes", "fixing","bugfix","patch", "repair", "repaired",
    "resolve", "resolved", "resolving", "recover", "restore",
    # 缺陷类
    "bug", "error", "fault", "failure", "crash", "defect",
    "incorrect", "wrong", "broken", "malfunction", "problem",
    "unstable","freeze", "leak", "timeout",
    "not work", "cannot start", "no longer work"
]

# 编译正则表达式（包含复合短语）
pattern = re.compile(
    r"\b(" + "|".join(map(re.escape, fix_keywords)) + r")\b",
    re.IGNORECASE
)

df_bugfix = df_pr[
    df_pr["title"].str.contains(pattern, na=False) |
    df_pr["description"].str.contains(pattern, na=False)
]

commit_records = []
seen_prs = set()

for _, pr_row in tqdm(df_bugfix.iterrows(), total=len(df_bugfix), desc="Fetching PR commits"):
    pr_num_raw = pr_row["number"]
    try:
        pr_num = int(pr_num_raw)
    except Exception:
        print(f"⚠️ 跳过无法解析的 PR 编号: {pr_num_raw}")
        continue

    if pr_num in seen_prs:
        continue
    seen_prs.add(pr_num)

    try:
        pr = repo.get_pull(pr_num)
        pr_created_at = pr.created_at.isoformat() if pr.created_at else None
        pr_merged_at = pr.merged_at.isoformat() if pr.merged_at else None

        for c in pr.get_commits():
            commit_records.append({
                "pr_number": pr_num,
                "pr_created_at": pr_created_at,
                "pr_merged_at": pr_merged_at,
                "commit_sha": c.sha,
                "commit_message": c.commit.message.replace("\n", " ")
            })
    except Exception as e:
        print(f"⚠️ 获取 PR #{pr_num} commits 失败: {e}")

df_commits = pd.DataFrame(commit_records)
if not df_commits.empty:
    df_commits["pr_number"] = df_commits["pr_number"].astype(int)

os.makedirs("data", exist_ok=True)
df_commits.to_csv("openpilot_pr_commit_links.csv", index=False, encoding="utf-8-sig")
df_bugfix.to_csv("openpilot_prs_bugfix.csv", index=False, encoding="utf-8-sig")

print(f"完成：{len(df_bugfix)} 修复类 PR，关联 {len(df_commits)} 条 commit。")
