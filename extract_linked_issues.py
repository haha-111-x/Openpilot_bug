import pandas as pd
import re
from tqdm import tqdm

print("正在分析 Issue 内部引用（PR / Commit 链接）...")

# 读取筛选后的已关闭、有评论的 Issue
df = pd.read_csv("openpilot_issues_closed_discussed.csv", encoding="utf-8-sig")

# 匹配 PR 引用 (#123 或完整 URL)
pattern_pr = re.compile(r"(?:https://github\.com/commaai/openpilot/pull/(\d+)|#(\d+))", re.I)
# 匹配 commit URL
pattern_commit = re.compile(r"https://github\.com/commaai/openpilot/commit/([0-9a-f]{6,40})", re.I)

def extract_links(text):
    """从文本中提取 PR 编号和 commit SHA"""
    if pd.isna(text):
        return {"pr_links": [], "commit_links": []}
    s = str(text)
    prs = [x for t in re.findall(pattern_pr, s) for x in t if x]
    commits = pattern_commit.findall(s)
    return {"pr_links": list(set(prs)), "commit_links": list(set(commits))}

tqdm.pandas()
df[["pr_links", "commit_links"]] = df.progress_apply(
    lambda r: pd.Series(extract_links(f"{r['title']} {r['description']} {r['comments']}")),
    axis=1
)

# 只保留含至少一个引用的 Issue
linked = df[(df["pr_links"].astype(bool)) | (df["commit_links"].astype(bool))]
linked.to_csv("openpilot_issues_with_links.csv", index=False, encoding="utf-8-sig")

print(f"\n完成：共 {len(linked)} 条 Issue 含 PR / Commit 引用")
