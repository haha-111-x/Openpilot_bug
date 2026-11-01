#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 7: 构建缺陷 URL ↔ 文件修改 数据集（支持 issue↔pr↔commit）
并额外提取 module_names（顶层）和 sub_module_names（第二层）
"""
import pandas as pd
import ast
from collections import defaultdict
from tqdm import tqdm

print("🚀 Step 7：生成 issue / PR URL 与 commit 修改文件映射 ...")

# === 1. 读取第6步结果 ===
df = pd.read_csv("openpilot_bug_dataset_final.csv", encoding="utf-8-sig")

# === 2. URL 构建逻辑（严格规则） ===
def build_url(row):
    issue_num = row.get("issue_number")
    pr_num = row.get("pr_number")

    def to_int_safe(x):
        try:
            return int(float(x))
        except:
            return None

    issue_num = to_int_safe(issue_num)
    pr_num = to_int_safe(pr_num)

    if issue_num is not None:
        return f"https://github.com/commaai/openpilot/issues/{issue_num}"
    elif pr_num is not None:
        return f"https://github.com/commaai/openpilot/pull/{pr_num}"
    else:
        return None

df["html_url"] = df.apply(build_url, axis=1)
df = df[df["html_url"].notna()].copy()

# === 3. 解析 commit 文件信息为列表 ===
def parse_filename(x):
    if pd.isna(x) or x in ("", "None"):
        return []
    if isinstance(x, str):
        if ";" in x:
            return [f.strip() for f in x.split(";") if f.strip()]
        try:
            val = ast.literal_eval(x)
            if isinstance(val, list):
                return [str(f).strip() for f in val if str(f).strip()]
            else:
                return [str(val).strip()]
        except:
            return [x.strip()]
    elif isinstance(x, list):
        return [str(f).strip() for f in x if str(f).strip()]
    else:
        return [str(x).strip()]

df["filename"] = df["filename"].apply(parse_filename)
df["file_count"] = pd.to_numeric(df["file_count"], errors="coerce").fillna(0).astype(int)

# === 4. 模块提取函数 ===
def extract_module(filepath: str) -> str:
    return filepath.split("/")[0] if "/" in filepath else filepath

def extract_sub_module(filepath: str) -> str:
    parts = filepath.split("/")
    return parts[1] if len(parts) > 1 else parts[0]

# === 5. 构建 file_changes 字段，并提取 module_names & sub_module_names ===
records = []

for url, group in tqdm(df.groupby("html_url"), desc="Aggregating file changes"):
    # 统计每个文件在 URL 下出现的总次数
    file_counter = defaultdict(int)
    for _, row in group.iterrows():
        filenames = list(set(row["filename"]))  # 同 commit 内重复文件只计一次
        for fname in filenames:
            file_counter[fname] += 1

    # 构建模块信息
    module_dict = defaultdict(lambda: {"module_name": None, "filename": [], "changes": 0})
    module_names_set = set()
    sub_module_names_set = set()

    for fname, count in file_counter.items():
        mod = extract_module(fname)
        sub_mod = extract_sub_module(fname)

        module_dict[mod]["module_name"] = mod
        module_dict[mod]["filename"].append({fname: count})
        module_dict[mod]["changes"] += count

        module_names_set.add(mod)
        sub_module_names_set.add(sub_mod)

    file_changes = {k: v for k, v in module_dict.items() if v["filename"]}
    records.append({
        "html_url": url,
        "file_changes": file_changes,
        "module_names": ",".join(sorted(module_names_set)),
        "sub_module_names": ",".join(sorted(sub_module_names_set))
    })

# === 6. 保存结果 ===
output_path = "openpilot_bug_filemap.csv"
pd.DataFrame(records).to_csv(output_path, index=False, encoding="utf-8-sig")

print(f"💾 已生成：{output_path} （共 {len(records)} 条 URL 对应文件修改 + 模块 + 子模块信息）")
