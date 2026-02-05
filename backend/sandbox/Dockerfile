# 多阶段构建：减小镜像体积，加快 docker run 启动
# 国内拉取失败时可传构建参数：--build-arg PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim
ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE} AS builder
# 不装 gcc，直接装 pandas/numpy（有预编译 wheel，无需编译）
RUN pip install --no-cache-dir --target /install pandas numpy

ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}
WORKDIR /app
# 只拷贝预编译好的包，不再装 gcc，镜像更小
COPY --from=builder /install /usr/local/lib/python3.11/site-packages
COPY runner.py /app/runner.py
ENTRYPOINT ["python", "-u", "/app/runner.py"]
