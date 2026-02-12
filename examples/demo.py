#!/usr/bin/env python3
"""
演示脚本：使用 dbprofile.sql（建表）+ CSV（数据）+ query.sql（要执行的 SQL）调用 POST /api/execute-sql。
先启动服务后执行：
  python examples/demo.py
  TRUSTED_COMPUTE_API=http://localhost:8000 python examples/demo.py
"""
from run_sql_examples import main

if __name__ == "__main__":
    main()
