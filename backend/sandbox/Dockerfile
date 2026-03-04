# Multi-stage build: smaller image, faster docker run
# If pull fails in China, pass: --build-arg PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim
ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}
WORKDIR /app

# 安装 MariaDB 客户端（提供 mysqldump）以及 Python 依赖。
# 说明：
# - 以 python:3.11-slim 为基础镜像，使用 apt 安装 mariadb-client 即可获得 mysqldump。
# - pandas/numpy/pymysql 仍通过 pip 安装。
RUN apt-get update \
    && apt-get install -y --no-install-recommends mariadb-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir pandas numpy pymysql

COPY runner.py /app/runner.py
ENTRYPOINT ["python", "-u", "/app/runner.py"]
