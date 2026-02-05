# 快速开始指南

## 前置要求

- Docker 和 Docker Compose
- 8GB+ 内存（用于运行多个容器）

### 若出现「pull access denied」或拉取 python 镜像失败

多为 Docker Hub 在国内访问受限。可任选其一：

1. **用国内镜像加速构建**（推荐）：  
   ```bash
   PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim NODE_IMAGE=docker.m.daocloud.io/library/node:18-alpine docker-compose up -d --build
   ```
   （前端拉取 node 镜像失败时，加上 `NODE_IMAGE=...` 同上。）
2. **配置 Docker 镜像加速**：在 Docker Desktop → Settings → Docker Engine 中增加 `"registry-mirrors": ["https://docker.m.daocloud.io"]`，保存后重试 `docker-compose up -d --build`。

## 启动项目

### 1. 克隆或进入项目目录

```bash
cd /Users/guigangwang/trusted-compute
```

### 2. 启动所有服务

```bash
# 首次运行建议加 --build，会构建 backend、frontend、沙箱镜像
docker-compose up -d --build
```

这将启动：
- MariaDB 数据库（端口 3306）
- 沙箱镜像构建（用于执行任务）
- 后端 API 服务（端口 8000）
- 前端 Web 界面（端口 3000）

**注意**：本机需已安装并运行 Docker，后端会挂载 `/var/run/docker.sock`，用于每次任务启动/销毁沙箱容器。

### 3. 等待服务启动

```bash
# 查看日志
docker-compose logs -f

# 或者检查服务状态
docker-compose ps
```

### 4. 访问应用

- **前端界面**: http://localhost:3000
- **后端API文档**: http://localhost:8000/docs
- **API根路径**: http://localhost:8000

## 使用示例

### 1. 创建项目

1. 打开 http://localhost:3000
2. 点击左侧菜单"创建项目"
3. 填写项目信息：
   - 项目名称：医疗数据分析项目
   - 项目描述：分析不同治疗方案的效果
4. 点击"创建项目"

### 2. 加入项目

1. 在项目列表中，点击"加入项目"按钮
2. 系统会自动创建一个参与者并加入项目

### 3. 创建计算任务

1. 在项目列表中，点击"查看任务"
2. 在任务创建区域，填写任务信息：
   - 任务名称：治疗方案效果分析
   - 模型类型：选择 SQL 或 Python
   - 输入代码：

**SQL示例：**
```sql
SELECT 
    category,
    COUNT(*) as count,
    AVG(value) as avg_value
FROM data_table
WHERE value > {{threshold}}
GROUP BY category
ORDER BY avg_value DESC;
```

**Python示例：**
```python
import pandas as pd

# 模拟数据
data = pd.DataFrame({
    'id': [1, 2, 3, 4],
    'value': [100, 200, 150, 300],
    'category': ['A', 'B', 'A', 'C']
})

# 计算逻辑
result = data.groupby('category').agg({
    'value': ['mean', 'sum', 'count']
}).reset_index()

result.columns = ['category', 'mean_value', 'sum_value', 'count']
result = result.to_dict('records')
```

3. 点击"创建任务"

### 4. 执行计算任务

1. 在任务列表中，找到创建的任务
2. 点击"执行任务"按钮
3. 输入执行参数（JSON格式）：
   ```json
   {"threshold": 100}
   ```
4. 点击"确定"执行

### 5. 查看结果

执行完成后，任务卡片下方会显示加密后的结果密文。结果已经过：
- 数据脱敏处理
- AES-256加密
- 哈希校验

## API 使用示例

### 使用 curl

```bash
# 创建项目
curl -X POST "http://localhost:8000/api/projects" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试项目",
    "description": "这是一个测试项目",
    "owner_id": "user_001"
  }'

# 获取项目列表
curl "http://localhost:8000/api/projects"

# 创建计算任务
curl -X POST "http://localhost:8000/api/projects/1/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "数据分析任务",
    "model_type": "sql",
    "model_code": "SELECT * FROM data WHERE value > {{threshold}}"
  }'

# 执行任务
curl -X POST "http://localhost:8000/api/tasks/1/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "input_params": {"threshold": 100}
  }'
```

### 使用 Python

```python
import requests

API_BASE = "http://localhost:8000"

# 创建项目
project = requests.post(f"{API_BASE}/api/projects", json={
    "name": "Python测试项目",
    "description": "使用Python API创建",
    "owner_id": "python_user"
}).json()

print(f"创建的项目ID: {project['id']}")

# 创建任务
task = requests.post(f"{API_BASE}/api/projects/{project['id']}/tasks", json={
    "name": "Python计算任务",
    "model_type": "python",
    "model_code": """
result = {
    'sum': sum([1, 2, 3, 4, 5]),
    'avg': sum([1, 2, 3, 4, 5]) / 5
}
"""
}).json()

print(f"创建的任务ID: {task['id']}")

# 执行任务
result = requests.post(f"{API_BASE}/api/tasks/{task['id']}/execute", json={
    "input_params": {}
}).json()

print(f"执行结果（密文）: {result['encrypted_result'][:50]}...")
```

## 停止服务

```bash
# 停止所有服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v
```

## 故障排查

### 端口被占用

如果端口被占用，可以修改 `docker-compose.yml` 中的端口映射。

### 数据库连接失败

检查 MariaDB 容器是否正常运行：
```bash
docker-compose ps mariadb
docker-compose logs mariadb
```

### 前端无法连接后端

检查环境变量 `REACT_APP_API_URL` 是否正确设置。

### 查看详细日志

```bash
# 查看所有服务日志
docker-compose logs

# 查看特定服务日志
docker-compose logs backend
docker-compose logs frontend
```

## 下一步

- 查看 [README.md](README.md) 了解项目架构
- 查看 [OPEN_SOURCE_SOLUTIONS.md](OPEN_SOURCE_SOLUTIONS.md) 了解开源方案
- 探索 API 文档：http://localhost:8000/docs
