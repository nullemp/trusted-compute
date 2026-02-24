# Multi-stage build: smaller image, faster docker run
# If pull fails in China, pass: --build-arg PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim
ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE} AS builder
# Install pandas/numpy and PyMySQL for MariaDB (no gcc)
RUN pip install --no-cache-dir --target /install pandas numpy pymysql

ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}
WORKDIR /app
# Copy prebuilt packages only; no gcc, smaller image
COPY --from=builder /install /usr/local/lib/python3.11/site-packages
COPY runner.py /app/runner.py
ENTRYPOINT ["python", "-u", "/app/runner.py"]
