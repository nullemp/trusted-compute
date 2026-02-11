# 离线镜像资源说明

本目录用于存放 **预先下载好的容器镜像 tar 文件**，以便在无法访问公网 Docker Hub 的内网环境中部署本项目。

> 说明：仓库本身不包含大体积镜像文件，需要在联网环境中由运维或开发同学提前准备好这些 tar 文件，再随安装包一起下发到内网。

## 一、需要的基础镜像

默认情况下，`docker-compose.yml` 使用以下镜像（可根据实际情况调整版本）：

- `mariadb:11`
- `python:3.11-slim`（通过 `PYTHON_IMAGE` 变量传入，用于构建 backend 与 sandbox 镜像）

## 二、在联网环境中导出镜像

在一台可以访问公网的构建机上执行（示例）：

```bash
docker pull mariadb:11
docker pull python:3.11-slim

mkdir -p runtime/images
docker save -o runtime/images/mariadb-11.tar mariadb:11
docker save -o runtime/images/python-3.11-slim.tar python:3.11-slim
```

然后将整个项目目录（包含 `runtime/images/*.tar`）打包，拷贝到内网环境。

## 三、在内网环境中导入镜像

在目标内网环境的主机上（已安装 Docker 或 Podman）执行：

```bash
cd /path/to/trusted-compute

docker load -i runtime/images/mariadb-11.tar
docker load -i runtime/images/python-3.11-slim.tar
```

导入成功后，再执行：

```bash
docker-compose up -d --build
```

由于基础镜像已经在本地镜像缓存中，构建和启动过程不会再访问公网。

> 若使用 Podman，可将上述命令中的 `docker` 替换为 `podman`。

## 四、镜像版本变更时的注意事项

- 若修改了 `docker-compose.yml` 中的 `MARIADB_IMAGE` 或 `PYTHON_IMAGE` 变量，或 backend/sandbox 的 `Dockerfile` 基础镜像，请同步更新：
  - 联网环境中的 `docker pull` / `docker save` 命令；
  - 本目录下 tar 文件的文件名（建议包含版本号，便于区分）。
- 确保离线环境导入的镜像版本与 compose/Dockerfile 中引用的版本一致。

