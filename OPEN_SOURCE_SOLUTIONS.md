# 开源可信计算/隐私计算方案

本文档介绍几个成熟的开源隐私计算框架，可以作为生产环境的参考方案。

## 1. FATE (Federated AI Technology Enabler)

### 简介
FATE是微众银行AI团队开源的一个工业级联邦学习框架，支持多种联邦学习算法。

### 特点
- 工业级实现，生产环境可用
- 支持多种联邦学习算法（逻辑回归、神经网络、树模型等）
- 提供完整的Web界面
- 支持多方参与
- 数据不出本地，模型参数加密传输

### 快速开始

```bash
# 使用Docker Compose部署
git clone https://github.com/FederatedAI/FATE.git
cd FATE/docker-deploy
bash install_standalone_docker.sh

# 访问Web界面
# http://localhost:8080
```

### 适用场景
- 联邦学习模型训练
- 多方数据联合建模
- 隐私保护的机器学习

### 文档
- GitHub: https://github.com/FederatedAI/FATE
- 文档: https://fate.readthedocs.io/

---

## 2. SecretFlow

### 简介
SecretFlow是蚂蚁集团开源的可信隐私计算框架，支持多方安全计算（MPC）、联邦学习、差分隐私等多种隐私计算技术。

### 特点
- 支持多种隐私计算技术
- Python友好的API
- 支持SPU（安全处理单元）加速
- 提供丰富的算法库

### 快速开始

```bash
# 安装
pip install secretflow

# 示例代码
import secretflow as sf

# 初始化
sf.init(['alice', 'bob', 'carol'], address='local')

# 创建数据
alice_data = sf.PYU('alice')(lambda: [1, 2, 3])()
bob_data = sf.PYU('bob')(lambda: [4, 5, 6])()

# 安全计算
result = alice_data + bob_data
print(result)
```

### 适用场景
- 多方安全计算
- 隐私数据分析
- 联合统计查询

### 文档
- GitHub: https://github.com/secretflow/secretflow
- 文档: https://www.secretflow.org.cn/

---

## 3. PySyft

### 简介
PySyft是OpenMined社区开源的联邦学习和隐私计算框架，基于PyTorch构建。

### 特点
- 基于PyTorch，易于集成
- 支持差分隐私
- 支持同态加密
- 活跃的社区

### 快速开始

```bash
# 安装
pip install syft

# 示例代码
import syft as sy
import torch

# 创建虚拟工作节点
hook = sy.TorchHook(torch)
alice = sy.VirtualWorker(hook, id="alice")
bob = sy.VirtualWorker(hook, id="bob")

# 创建数据
data = torch.tensor([1, 2, 3, 4, 5])
data_ptr = data.send(alice)

# 远程计算
result_ptr = data_ptr + data_ptr
result = result_ptr.get()
```

### 适用场景
- 联邦学习研究
- 隐私保护的深度学习
- 原型开发

### 文档
- GitHub: https://github.com/OpenMined/PySyft
- 文档: https://www.openmined.org/

---

## 4. TEE (Trusted Execution Environment) 方案

### Intel SGX
- 硬件级别的可信执行环境
- 数据在加密内存中处理
- 需要支持SGX的硬件

### 使用场景
- 需要最高安全级别的场景
- 硬件支持的环境

---

## 5. 本项目 vs 开源方案

| 特性 | 本项目 | FATE | SecretFlow | PySyft |
|------|--------|------|------------|--------|
| 复杂度 | 低 | 高 | 中 | 中 |
| 生产就绪 | 否（演示） | 是 | 是 | 部分 |
| 联邦学习 | 否 | 是 | 是 | 是 |
| 多方安全计算 | 否 | 部分 | 是 | 部分 |
| SQL支持 | 是 | 否 | 是 | 否 |
| Python脚本 | 是 | 是 | 是 | 是 |
| Web界面 | 是 | 是 | 否 | 否 |

## 推荐使用场景

1. **学习和理解概念**：使用本项目
2. **生产环境 - 联邦学习**：使用 FATE
3. **生产环境 - 通用隐私计算**：使用 SecretFlow
4. **研究和原型**：使用 PySyft

## 部署开源方案示例

### FATE 部署示例

创建 `fate-docker-compose.yml`:

```yaml
version: '3.8'

services:
  fate-board:
    image: federatedai/fate-board:latest
    ports:
      - "8080:8080"
    environment:
      FATE_FLOW_HOST: fate-flow
      FATE_FLOW_PORT: 9380
    depends_on:
      - fate-flow

  fate-flow:
    image: federatedai/fate-flow:latest
    ports:
      - "9380:9380"
    environment:
      FATE_FLOW_DB: postgresql://fate:fate@postgres:5432/fate_flow
    depends_on:
      - postgres

  postgres:
    image: postgres:13
    environment:
      POSTGRES_USER: fate
      POSTGRES_PASSWORD: fate
      POSTGRES_DB: fate_flow
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

运行：
```bash
docker-compose -f fate-docker-compose.yml up -d
```

### SecretFlow 部署示例

创建 `secretflow-demo.py`:

```python
import secretflow as sf
from secretflow.data import FedNdarray, PartitionWay
from secretflow.ml.linear import SSLR

# 初始化
sf.init(['alice', 'bob'], address='local')

# 准备数据
alice_data = sf.PYU('alice')(lambda: [[1, 2], [3, 4]])()
bob_data = sf.PYU('bob')(lambda: [[5, 6], [7, 8]])()

# 联邦学习训练
model = SSLR()
model.fit(alice_data, bob_data, y=[1, 0])
```

运行：
```bash
python secretflow-demo.py
```

## 总结

本项目提供了一个简化的可信模型计算平台实现，适合：
- 理解可信计算的基本概念
- 快速原型开发
- 学习和教学

对于生产环境，建议使用成熟的开源方案如 FATE 或 SecretFlow，它们提供了：
- 更强的安全保障
- 更完善的算法库
- 更好的性能优化
- 更活跃的社区支持
