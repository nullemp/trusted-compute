# Multi-stage build: smaller image, faster docker run
# If pull fails in China, pass: --build-arg PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim
ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}
WORKDIR /app

# Preinstall pandas/numpy/pymysql；SM4 使用纯 Python 实现，无需 C 编译工具链
RUN pip install --no-cache-dir pandas numpy pymysql

COPY runner.py /app/runner.py
ENTRYPOINT ["python", "-u", "/app/runner.py"]
