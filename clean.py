import pandas as pd
import ast
import os
from github import Github, Auth
from dotenv import load_dotenv
from tqdm import tqdm

print("清洗 + 聚合缺陷数据（含文件名信息）...")

relations_df = pd.read_csv("openpilot_bug_fix_dataset.csv", encoding="utf-8-sig")
issues_df = pd.read_csv("openpilot_issues_prs.csv", encoding="utf-8-sig")

def to_int_nullable(series):
    try:
        return pd.to_numeric(series, errors="coerce").astype("Int64")
    except Exception:
        return series

if "pr_number" in relations_df.columns:
    relations_df["pr_number"] = to_int_nullable(relations_df["pr_number"])
if "issue_number" in relations_df.columns:
    relations_df["issue_number"] = to_int_nullable(relations_df["issue_number"])

relations_df["commit_sha"] = relations_df["commit_sha"].astype(str).str.strip()
relations_df = relations_df[relations_df["commit_sha"].notna() & (relations_df["commit_sha"] != "")]

print("\n原始关系分布：")
print(relations_df["relation_type"].value_counts())

agg_rows = []

# issue 相关
issue_related = relations_df[relations_df["relation_type"].isin(["issue↔pr↔commit", "issue↔commit"])]
if not issue_related.empty:
    issue_grouped = issue_related.groupby("issue_number", as_index=False).agg({
        "pr_number": lambda x: sorted(set(x.dropna())),
        "commit_sha": lambda x: sorted(set(x.dropna())),
        "relation_type": lambda x: ", ".join(sorted(set(x.dropna()))),
        "issue_created_at": "first",
        "issue_closed_at": "first",
        "pr_created_at": "first",
        "pr_merged_at": "first"
    })
    issue_grouped["entity_type"] = "issue"
    agg_rows.append(issue_grouped)

# pr 相关
pr_related = relations_df[relations_df["relation_type"] == "pr↔commit"]
if not pr_related.empty:
    pr_grouped = pr_related.groupby("pr_number", as_index=False).agg({
        "commit_sha": lambda x: sorted(set(x.dropna())),
        "relation_type": lambda x: ", ".join(sorted(set(x.dropna()))),
        "pr_created_at": "first",
        "pr_merged_at": "first"
    })
    pr_grouped["entity_type"] = "pr"
    agg_rows.append(pr_grouped)

# 合并
if not agg_rows:
    raise ValueError("没有可聚合的关系！")
agg_df = pd.concat(agg_rows, ignore_index=True, sort=False)

issues_core = issues_df.rename(columns={"number": "issue_number"})[
    ["issue_number", "title", "description", "labels", "created_at", "closed_at"]
]
final_df = agg_df.merge(issues_core, on="issue_number", how="left")

columns_order = [
    "entity_type", "relation_type",
    "issue_number", "pr_number",
    "title", "description", "labels",
    "issue_created_at", "issue_closed_at",
    "pr_created_at", "pr_merged_at",
    "commit_sha"
]
for col in columns_order:
    if col not in final_df.columns:
        final_df[col] = None
final_df = final_df[columns_order]

print("\n正在提取 commit 修改文件名...")

# 初始化 GitHub
load_dotenv()
auth = Auth.Token(os.getenv("GITHUB_TOKEN"))
g = Github(auth=auth)
repo = g.get_repo("commaai/openpilot")

# 展开 commit 列
def parse_commit_list(x):
    # 统一解析为列表类型
    try:
        # 先直接处理 None 或空字符串
        if x is None:
            return []
        if isinstance(x, float) and pd.isna(x):
            return []
        # 如果本身是 list 或 array，直接转为字符串列表
        if isinstance(x, (list, tuple, set)):
            return [str(i).strip() for i in x if str(i).strip()]
        # 如果是字符串形式的列表
        if isinstance(x, str):
            if x.strip() in ("", "[]", "nan"):
                return []
            try:
                val = ast.literal_eval(x)
                if isinstance(val, (list, tuple, set)):
                    return [str(i).strip() for i in val if str(i).strip()]
                else:
                    return [str(val).strip()]
            except Exception:
                return [x.strip()]
        return [str(x).strip()]
    except Exception:
        return []


final_df["commit_sha"] = final_df["commit_sha"].apply(parse_commit_list)
df_exploded = final_df.explode("commit_sha").reset_index(drop=True)
df_exploded = df_exploded[df_exploded["commit_sha"].notna() & (df_exploded["commit_sha"] != "")]

commits = sorted(set(df_exploded["commit_sha"].dropna().astype(str)))
print(f"共 {len(commits)} 个唯一 commit 待提取文件信息")

commit_to_files, commit_to_count = {}, {}

for sha in tqdm(commits, desc="Fetching commit files"):
    if not sha or sha == "nan":
        continue
    try:
        commit = repo.get_commit(sha)
        files = [f.filename for f in commit.files]
        commit_to_files[sha] = ";".join(files) if files else None
        commit_to_count[sha] = len(files) if files else 0
    except Exception as e:
        commit_to_files[sha] = None
        commit_to_count[sha] = 0
        print(f"无法获取 {sha}: {e}")

df_exploded["filename"] = df_exploded["commit_sha"].map(commit_to_files)
df_exploded["file_count"] = df_exploded["commit_sha"].map(commit_to_count)

print("\n清洗后关系分布：")
print(final_df["relation_type"].value_counts())

if "commit_only" in final_df["relation_type"].unique():
    print("警告：发现 commit_only，请检查 Step5。")
else:
    print("数据完整性检查通过。")

output_path = "openpilot_bug_dataset_final.csv"
df_exploded.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"已保存：{output_path}（共 {len(df_exploded)} 条记录，含 filename + file_count）")


