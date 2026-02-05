# 构建时发生了什么？—— 配置文件与流程说明

当你执行 `docker-compose up -d --build` 时，Docker 会按依赖关系**先构建镜像、再启动容器**。下面按「谁在指挥」「谁被用」说明各配置文件的作用，以及构建时具体发生了什么。

---

## 一、总览：谁在指挥、谁被用

| 文件 | 作用（一句话） |
|------|----------------|
| **docker-compose.yml** | 总指挥：定义有哪些服务、用什么镜像/怎么构建、端口、环境变量、依赖顺序。 |
| **backend/Dockerfile** | 定义「后端镜像」怎么从零构建出来（基于谁、装什么、复制哪些代码）。 |
| **backend/sandbox/Dockerfile** | 定义「沙箱镜像」怎么构建（跑任务用的隔离环境）。 |
| **frontend/Dockerfile** | 定义「前端镜像」怎么构建（基于 Node、装依赖、复制代码）。 |
| **backend/requirements.txt** | 后端 Python 依赖列表，被 backend 的 Dockerfile 里的 `pip install -r requirements.txt` 使用。 |
| **frontend/package.json** | 前端 Node 依赖和脚本，被 frontend 的 Dockerfile 里的 `npm install` 和 `npm start` 使用。 |

构建时：**docker-compose 根据 yml 里每个服务的 `build` 配置，在对应目录下用对应的 Dockerfile 构建镜像**；`requirements.txt` 和 `package.json` 是在 Dockerfile 里被显式使用的，不是 Docker 自动发现的。

---

## 二、执行 `docker-compose up -d --build` 时发生了什么（按顺序）

### 1. 读取 docker-compose.yml

Docker Compose 会：

- 解析 `version` 和所有 `services`。
- 看到 4 个服务：`mariadb`、`sandbox`、`backend`、`frontend`。
- 对**需要构建**的服务（有 `build` 的）：用 `build.context` 作为上下文目录、`build.dockerfile` 指定 Dockerfile、`build.args` 传给 Dockerfile 里的 ARG。

### 2. 拉取/构建镜像（无依赖的服务先来）

- **mariadb**  
  - 没有 `build`，只有 `image: mariadb:11`。  
  - 所以只是**拉取**现成的镜像 `mariadb:11`，不执行任何 Dockerfile。

- **sandbox**  
  - 有 `build: context: ./backend/sandbox, dockerfile: Dockerfile`。  
  - 在项目根目录下执行「在 `./backend/sandbox` 里用该目录的 `Dockerfile` 构建镜像」，构建出的镜像名为 `image: trusted-compute-sandbox`。  
  - 构建过程见下一节「各 Dockerfile 在做什么」。

- **backend**  
  - 有 `build: context: ./backend, dockerfile: Dockerfile`。  
  - 在 `./backend` 目录下用 `backend/Dockerfile` 构建，镜像名由 compose 默认生成（如 `trusted-compute-backend`）。  
  - 会用到 `backend/requirements.txt`（在 Dockerfile 里被 `COPY` 和 `pip install -r requirements.txt` 使用）。

- **frontend**  
  - 有 `build: context: ./frontend, dockerfile: Dockerfile`。  
  - 在 `./frontend` 下用 `frontend/Dockerfile` 构建。  
  - 会用到 `frontend/package.json`（在 Dockerfile 里被 `COPY` 和 `npm install` 使用）。

构建顺序上，没有 `depends_on` 的会先构建；有 `depends_on` 的会在被依赖方之后构建，但**镜像构建**一般不等待其他容器，只有**启动**才按依赖顺序（例如 backend 等 mariadb healthy）。

### 3. 启动容器（按依赖顺序）

- 先启动 **mariadb**，等其 `healthcheck` 通过。  
- 再启动 **backend**（依赖 mariadb healthy）。  
- 再启动 **frontend**（依赖 backend，但只表示启动顺序，不表示要 backend 健康才起）。  
- **sandbox** 的 `command: ["true"]` 表示容器一启动就执行 `true` 然后退出，所以容器会立刻退出；**镜像已经建好**，之后 backend 里执行任务时会用 `docker run ... trusted-compute-sandbox` 按需起临时容器。

所以：**构建阶段**主要是「拉 mariadb 镜像 + 按三个 Dockerfile 构建三个镜像」；**运行阶段**是「起 mariadb → 起 backend → 起 frontend，sandbox 只提供镜像不常驻」。

---

## 三、各 Dockerfile 在构建时具体做了什么

### 1. backend/Dockerfile（后端镜像）

- **ARG PYTHON_IMAGE**  
  默认 `python:3.11-slim`；可在 docker-compose 里用 `build.args.PYTHON_IMAGE` 覆盖（如国内镜像）。

- **FROM ${PYTHON_IMAGE}**  
  基于该 Python 镜像，得到一个 Linux + Python 环境。

- **RUN for f in ... sed ...**  
  把系统里 apt 的源改成国内镜像（阿里云），方便后面 `apt-get` 能拉包。

- **RUN apt-get update && apt-get install ... curl ...**  
  装 `ca-certificates`、`curl`，然后用 curl 下载 Docker 官方给的静态编译好的 **Docker CLI**（docker 命令），放到 `/usr/local/bin/docker`。这样容器里没有 Docker 守护进程，但可以通过挂载宿主机的 ` /var/run/docker.sock` 来执行 `docker run`（在宿主机上起沙箱容器）。

- **COPY requirements.txt .**  
  把本地的 `backend/requirements.txt` 复制进镜像当前目录（/app）。

- **RUN pip install --no-cache-dir -r requirements.txt**  
  在镜像里安装 requirements.txt 里列出的所有 Python 包（FastAPI、uvicorn、sqlalchemy、pymysql 等）。**这里用到的是 requirements.txt 这一份配置文件。**

- **COPY . .**  
  把 `backend/` 下除 .dockerignore 排除外的所有文件复制进镜像的 /app（包括 main.py、models、services 等）。

- **EXPOSE 8000 / CMD ...**  
  声明端口和启动命令：容器起来后执行 `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`。

所以：**构建后端镜像时**，用到的「配置文件」就是 **requirements.txt**；**docker-compose.yml** 里只是告诉 Docker「用 backend 目录 + 这个 Dockerfile 来构建」，并可通过 `build.args` 传入 `PYTHON_IMAGE`。

### 2. backend/sandbox/Dockerfile（沙箱镜像）

- **ARG PYTHON_IMAGE / FROM ${PYTHON_IMAGE} AS builder**  
  第一个阶段：基于同一 Python 镜像，当作「构建阶段」。

- **RUN pip install --no-cache-dir --target /install pandas numpy**  
  把 pandas、numpy 装到目录 `/install`，不装进系统 site-packages。这样下一阶段只拷贝这一坨，镜像更小。

- **FROM ${PYTHON_IMAGE}**（第二阶段）  
  再开一个干净的 Python 镜像，不要 builder 里的 gcc 等。

- **COPY --from=builder /install ...**  
  把 builder 里 `/install` 下的包拷贝到当前镜像的 site-packages，所以最终镜像里只有 Python + pandas/numpy，没有编译工具。

- **COPY runner.py /app/runner.py**  
  把沙箱入口脚本拷进去。

- **ENTRYPOINT ["python", "-u", "/app/runner.py"]**  
  以后任何人 `docker run ... trusted-compute-sandbox` 时，容器里就只跑这个 Python 脚本；stdin 读 JSON，stdout 写结果。

这里**没有**用到 requirements.txt；依赖是写死在 Dockerfile 的 `pip install pandas numpy` 里的。**配置文件**只有「Dockerfile 本身」和 docker-compose 里传进来的 `PYTHON_IMAGE`。

### 3. frontend/Dockerfile（前端镜像）

- **ARG NODE_IMAGE / FROM ${NODE_IMAGE}**  
  基于 Node 镜像（默认 node:18-alpine），可用 docker-compose 的 `NODE_IMAGE` 覆盖。

- **COPY package*.json ./**  
  把 `frontend/package.json`（和若有 package-lock.json）拷进镜像的 /app。**这里用到的就是 package.json 这一份配置文件。**

- **RUN npm install**  
  在镜像里执行 npm install，根据 package.json 和 lock（若有）安装所有依赖（react、antd、axios、react-scripts 等）。**所以前端依赖完全由 package.json（及 lock）决定。**

- **COPY . .**  
  再把前端源码（src、public 等）拷进去。

- **EXPOSE 3000 / CMD ["npm", "start"]**  
  容器启动后执行 `npm start`，即 package.json 里 scripts.start（通常是 react-scripts start），起开发服务器。

所以：**构建前端镜像时**，用到的「配置文件」就是 **package.json**（以及可选的 package-lock.json）；docker-compose 只负责指定「用哪个目录、哪个 Dockerfile、传什么 NODE_IMAGE」。

---

## 四、各配置文件分别给谁用、在什么时候用

- **docker-compose.yml**  
  - **给谁用**：Docker Compose（你执行的 `docker-compose` 命令）。  
  - **什么时候用**：每次你执行 `docker-compose up/build` 时都会读。  
  - **作用**：定义服务、构建方式、环境变量、挂载、依赖；构建时根据里面的 `build` 去调各个 Dockerfile。

- **backend/requirements.txt**  
  - **给谁用**：backend 的 Dockerfile 里的 `pip install -r requirements.txt`。  
  - **什么时候用**：**只在构建 backend 镜像**时用（在 RUN 那一步）。  
  - **作用**：列出后端 Python 依赖及版本，保证镜像里装的是同一套包。

- **frontend/package.json**  
  - **给谁用**：frontend 的 Dockerfile 里的 `npm install`，以及容器里 `npm start`。  
  - **什么时候用**：**构建 frontend 镜像**时（COPY + npm install），以及**容器运行时**（npm start 读 scripts）。  
  - **作用**：依赖列表、脚本命令、项目名等；前端依赖和启动方式都由它决定。

- **backend/Dockerfile、backend/sandbox/Dockerfile、frontend/Dockerfile**  
  - **给谁用**：Docker 引擎在「构建镜像」时用。  
  - **什么时候用**：当 docker-compose 对该服务执行 build 时（例如 `docker-compose up -d --build` 或 `docker-compose build backend`）。  
  - **作用**：从零定义怎么生成镜像（基于谁、装什么、复制什么、怎么启动）。

- **环境变量（在 docker-compose 的 environment 里）**  
  - 例如 `DATABASE_URL`、`REACT_APP_API_URL`、`SANDBOX_IMAGE`。  
  - **给谁用**：运行中的**容器**里的应用（Python 的 os.getenv、React 的 process.env.REACT_APP_*）。  
  - **什么时候用**：**不参与构建**，只在**容器启动后**被进程读到。  
  - 注意：`REACT_APP_API_URL` 在「构建时」被前端打包进静态资源（很多 React 模板在 build 时读 env），所以如果你改了这个变量，有时需要重新 build 前端镜像才会生效。

---

## 五、一条命令串联起来（小结）

你执行：

```bash
PYTHON_IMAGE=... NODE_IMAGE=... docker-compose up -d --build
```

时，顺序可以简化为：

1. **读 docker-compose.yml**，确定要拉/建哪些镜像、起哪些容器、依赖关系。
2. **拉取 mariadb:11**（不构建）。
3. **构建 sandbox 镜像**：在 `backend/sandbox` 用其 Dockerfile，用 PYTHON_IMAGE 做基础镜像，装 pandas/numpy，拷 runner.py，得到 `trusted-compute-sandbox`。
4. **构建 backend 镜像**：在 `backend` 用其 Dockerfile，用 PYTHON_IMAGE 做基础镜像，改 apt 源、装 curl、下 Docker CLI、按 **requirements.txt** 装 Python 包、拷代码，得到后端镜像。
5. **构建 frontend 镜像**：在 `frontend` 用其 Dockerfile，用 NODE_IMAGE 做基础镜像，拷 **package.json**、执行 npm install、拷源码，得到前端镜像。
6. **启动容器**：先 mariadb，等健康；再 backend；再 frontend；sandbox 容器执行 `true` 后退出（只留镜像）。

所以：**构建时**真正参与进来的「配置文件」主要是 **docker-compose.yml、三个 Dockerfile、requirements.txt、package.json**；其它如 `.dockerignore` 只是影响 COPY 时哪些文件不打进镜像，不改变构建逻辑。  
如果你愿意，下一步可以针对「某一份文件」逐段说明（例如只讲 docker-compose.yml 或只讲 backend 的 Dockerfile）方便你对着看。
