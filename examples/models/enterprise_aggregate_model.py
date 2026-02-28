#!/usr/bin/env python3
"""
企业示例聚合模型（在 sandbox 内执行的 Python 脚本）。

约定：
- 外部通过 /api/python-from-files 上传本文件作为 model_file
- data_file 为 enterprise_dump.json（或结构兼容的 JSON），其中 data.sales_orders / data.employees / data.departments 可用

输出：
- result 为 pandas.DataFrame：按 region + product_id 聚合销售订单
"""

import pandas as pd

data = input_params["data"]

orders = pd.DataFrame(data["sales_orders"])
employees = pd.DataFrame(data["employees"])
departments = pd.DataFrame(data["departments"])

# 订单 -> 员工 -> 部门
df = (
    orders
    .merge(employees, left_on="employee_id", right_on="id", suffixes=("", "_emp"))
    .merge(
        departments[["id", "name", "region"]],
        left_on="dept_id",
        right_on="id",
        suffixes=("", "_dept"),
    )
)

grouped = (
    df.groupby(["region", "product_id"], as_index=False)
    .agg(
        total_amount=("amount", "sum"),
        avg_amount=("amount", "mean"),
        order_count=("id", "count"),
    )
    .sort_values(["region", "total_amount"], ascending=[True, False])
)

result = grouped

