#!/usr/bin/env python3
"""生成企业示例数据：5 张表，每表不少于 100 行。输出：enterprise_data.json、enterprise_dump.sql、enterprise_dump.json（mysqldump 风格 SQL + JSON 版 DDL+数据）。"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 与 _write_dump_sql 一致的 DDL 文本，供 JSON dump 使用
_DDL_BY_TABLE = {
    "departments": """CREATE TABLE IF NOT EXISTS departments (
  id INT,
  name VARCHAR(255),
  parent_id INT,
  budget DOUBLE,
  region VARCHAR(64)
);""",
    "employees": """CREATE TABLE IF NOT EXISTS employees (
  id INT,
  name VARCHAR(255),
  dept_id INT,
  job_title VARCHAR(128),
  salary DOUBLE,
  hire_date VARCHAR(32)
);""",
    "projects": """CREATE TABLE IF NOT EXISTS projects (
  id INT,
  name VARCHAR(255),
  dept_id INT,
  manager_id INT,
  budget DOUBLE,
  start_date VARCHAR(32),
  end_date VARCHAR(32),
  status VARCHAR(64)
);""",
    "products": """CREATE TABLE IF NOT EXISTS products (
  id INT,
  name VARCHAR(255),
  category VARCHAR(128),
  unit_price DOUBLE
);""",
    "sales_orders": """CREATE TABLE IF NOT EXISTS sales_orders (
  id INT,
  customer_name VARCHAR(255),
  employee_id INT,
  product_id INT,
  quantity INT,
  order_date VARCHAR(32),
  amount DOUBLE
);""",
}


def _sql_escape(val) -> str:
    """单个值转 SQL 字面量：NULL、数字、字符串（单引号加倍）。"""
    if val is None:
        return "NULL"
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return str(val) if val == val else "NULL"  # NaN
    s = str(val)
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def _row_to_sql_values(cols: list, row: dict) -> str:
    """一行 dict 转为 VALUES (v1,v2,...) 的括号部分。"""
    return "(" + ",".join(_sql_escape(row.get(c)) for c in cols) + ")"


def _write_dump_sql(out_path: Path, tables: list) -> None:
    """写入 mysqldump 风格单文件：DDL + INSERT INTO ... VALUES (...),(...);"""
    lines = [
        "-- MariaDB/MySQL dump: 企业示例（DDL + 数据）",
        "-- 可用 mysql -u user -p dbname < enterprise_dump.sql 导入",
        "",
    ]
    ddl_sql = "\n".join(_DDL_BY_TABLE[spec["table_name"]] for spec in tables)
    lines.append(ddl_sql.strip())
    lines.append("")

    for spec in tables:
        name = spec["table_name"]
        data = spec.get("data") or []
        if not data:
            continue
        cols = list(data[0].keys()) if isinstance(data[0], dict) else []
        if not cols:
            continue
        col_list = ",".join(f"`{c}`" for c in cols)
        # 每批约 50 行，避免单行过长
        batch_size = 50
        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            values = ",".join(_row_to_sql_values(cols, r) for r in batch)
            lines.append(f"INSERT INTO `{name}` ({col_list}) VALUES {values};")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def _write_dump_json(out_path: Path, tables: list) -> None:
    """写入 mysqldump 风格的 JSON：metadata + schema(DDL) + data，单文件。"""
    schema = {spec["table_name"]: _DDL_BY_TABLE.get(spec["table_name"], "") for spec in tables}
    data = {spec["table_name"]: spec.get("data") or [] for spec in tables}
    payload = {
        "metadata": {
            "description": "MariaDB/MySQL dump in JSON (schema + data)",
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "gen_enterprise_data.py",
        },
        "schema": schema,
        "data": data,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# 固定种子便于复现
random.seed(42)

DEPARTMENTS = [
    "华东销售部", "华南销售部", "华北销售部", "西南销售部", "研发一部", "研发二部",
    "产品部", "市场部", "人力资源部", "财务部", "运营部", "客服部", "供应链部", "法务部",
]
REGIONS = ["华东", "华南", "华北", "西南", "华中", "西北", "东北"]
JOB_TITLES = ["销售经理", "销售代表", "研发工程师", "产品经理", "市场专员", "财务主管", "HR专员", "运营专员", "客服主管", "采购专员"]
PROJECT_PREFIXES = ["数字化转型", "客户平台", "供应链优化", "数据分析", "安全加固", "移动端", "API网关", "营销自动化"]
STATUSES = ["进行中", "已验收", "暂停", "规划中"]
PRODUCT_CATEGORIES = ["软件服务", "硬件设备", "云服务", "咨询服务", "培训", "运维支持"]
CUSTOMER_PREFIXES = ["集团", "科技", "制造", "零售", "医疗", "教育", "金融", "物流"]


def random_date(start: datetime, end: datetime) -> str:
    d = start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))
    return d.strftime("%Y-%m-%d")


def gen_departments(n: int = 105) -> list:
    rows = []
    for i in range(1, n + 1):
        name = DEPARTMENTS[(i - 1) % len(DEPARTMENTS)] + (f"-{i}" if i > len(DEPARTMENTS) else "")
        parent_id = random.randint(1, min(20, i - 1)) if i > 1 else None
        rows.append({
            "id": i,
            "name": name,
            "parent_id": parent_id,
            "budget": round(random.uniform(50, 500), 2),
            "region": random.choice(REGIONS),
        })
    return rows


def gen_employees(n: int = 105, max_dept: int = 105) -> list:
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "id": i,
            "name": f"员工{i}",
            "dept_id": random.randint(1, max_dept),
            "job_title": random.choice(JOB_TITLES),
            "salary": round(random.uniform(8, 45), 2),
            "hire_date": random_date(datetime(2018, 1, 1), datetime(2024, 6, 1)),
        })
    return rows


def gen_projects(n: int = 105, max_dept: int = 105, max_emp: int = 105) -> list:
    rows = []
    for i in range(1, n + 1):
        name = random.choice(PROJECT_PREFIXES) + str(i)
        start = random_date(datetime(2022, 1, 1), datetime(2024, 1, 1))
        end = random_date(datetime(2024, 1, 1), datetime(2025, 12, 31))
        rows.append({
            "id": i,
            "name": name,
            "dept_id": random.randint(1, max_dept),
            "manager_id": random.randint(1, max_emp),
            "budget": round(random.uniform(20, 200), 2),
            "start_date": start,
            "end_date": end,
            "status": random.choice(STATUSES),
        })
    return rows


def gen_products(n: int = 105) -> list:
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "id": i,
            "name": f"产品{i}-{random.choice(PRODUCT_CATEGORIES)}",
            "category": random.choice(PRODUCT_CATEGORIES),
            "unit_price": round(random.uniform(100, 5000), 2),
        })
    return rows


def gen_sales_orders(n: int = 105, max_emp: int = 105, max_prod: int = 105) -> list:
    rows = []
    for i in range(1, n + 1):
        qty = random.randint(1, 50)
        unit_price = round(random.uniform(100, 3000), 2)
        amount = round(qty * unit_price * (0.95 + random.random() * 0.1), 2)
        rows.append({
            "id": i,
            "customer_name": random.choice(CUSTOMER_PREFIXES) + f"公司{i % 50}",
            "employee_id": random.randint(1, max_emp),
            "product_id": random.randint(1, max_prod),
            "quantity": qty,
            "order_date": random_date(datetime(2023, 1, 1), datetime(2024, 12, 1)),
            "amount": amount,
        })
    return rows


def main():
    out_dir = Path(__file__).resolve().parent
    depts = gen_departments(105)
    emps = gen_employees(105, len(depts))
    projs = gen_projects(105, len(depts), len(emps))
    prods = gen_products(105)
    orders = gen_sales_orders(105, len(emps), len(prods))

    tables = [
        {"table_name": "departments", "data": depts},
        {"table_name": "employees", "data": emps},
        {"table_name": "projects", "data": projs},
        {"table_name": "products", "data": prods},
        {"table_name": "sales_orders", "data": orders},
    ]
    payload = {"tables": tables}
    out_json = out_dir / "enterprise_data.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    out_dump_sql = out_dir / "enterprise_dump.sql"
    _write_dump_sql(out_dump_sql, tables)
    out_dump_json = out_dir / "enterprise_dump.json"
    _write_dump_json(out_dump_json, tables)
    print(f"已生成 {out_json}，5 张表行数: departments={len(depts)}, employees={len(emps)}, projects={len(projs)}, products={len(prods)}, sales_orders={len(orders)}")
    print(f"已生成 {out_dump_sql}（mysqldump 风格 SQL，可用 mysql < enterprise_dump.sql 导入）")
    print(f"已生成 {out_dump_json}（mysqldump 风格 JSON：metadata + schema + data）")


if __name__ == "__main__":
    main()
