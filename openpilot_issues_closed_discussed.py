import pandas as pd

# 1. 读取上一步导出的 CSV
df = pd.read_csv("openpilot_issues_prs.csv")

# 2. 筛选条件：
#   - 不是 Pull Request（is_pull_request == False）
#   - 状态为已关闭（state == 'closed'）
#   - 至少有一条评论（comments_count > 0）
closed_discussed_issues = df[
    (df["is_pull_request"] == False) &
    (df["state"] == "closed") &
    (df["comments_count"] > 0)
]

# 3. 保存结果
closed_discussed_issues.to_csv("openpilot_issues_closed_discussed.csv", index=False, encoding="utf-8-sig")
print(f"完成筛选，共 {len(closed_discussed_issues)} 条记录已保存到 openpilot_issues_closed_discussed.csv")
