# 国内拉取失败时可传构建参数：--build-arg PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim
ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}

WORKDIR /app

# 使用国内 Debian 源（兼容 sources.list 与 sources.list.d/debian.sources）
RUN for f in /etc/apt/sources.list /etc/apt/sources.list.d/debian.sources; do \
      test -f "$f" && sed -i 's|deb.debian.org|mirrors.aliyun.com|g' "$f" && sed -i 's|security.debian.org/debian-security|mirrors.aliyun.com/debian-security|g' "$f"; \
    done

# 只装 curl + ca-certificates，再下载 Docker CLI（不装 gcc，避免大包拉取失败）
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && DOCKER_ARCH=$(dpkg --print-architecture) \
    && [ "$DOCKER_ARCH" = "amd64" ] && DOCKER_ARCH=x86_64 || true \
    && [ "$DOCKER_ARCH" = "arm64" ] && DOCKER_ARCH=aarch64 || true \
    && curl -fsSL "https://download.docker.com/linux/static/stable/${DOCKER_ARCH}/docker-24.0.7.tgz" | tar xz -C /tmp \
    && mv /tmp/docker/docker /usr/local/bin/docker \
    && rm -rf /tmp/docker \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
