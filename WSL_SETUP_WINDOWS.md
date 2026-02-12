## Windows 下 WSL 安装指南（用于 Podman）

本项目使用 **Windows 上的 Podman**，而 Podman 依赖 **WSL（适用于 Linux 的 Windows 子系统）** 以及至少一个 Linux 发行版（例如 Ubuntu）。

若启动脚本检测到 WSL 未就绪，会停止启动 Podman 并提示你查看本文件。

---

### 1. 检查是否已安装 WSL

以普通用户身份打开 **PowerShell** 或 **cmd**，执行：

```powershell
wsl -l -v
```

若列表中至少有一个发行版（例如 `Ubuntu`），说明 WSL 已安装可用。

若出现 **“未安装任何发行版”** 或报错，请按下面步骤操作。

---

### 2. Windows 版本对 WSL2 的支持

仅部分 Windows 版本支持 WSL2，概览如下：

| Windows 版本         | 最低版本 / 内部版本号                     | 支持 WSL2     | 说明                                          |
| -------------------- | ----------------------------------------- | ------------- | --------------------------------------------- |
| **Windows 11** | 任意（所有内部版本）                      | 是            | `wsl --install` 默认安装 WSL2。             |
| **Windows 10** | 版本 1903，内部版本**18362** 及以上 | 是            | 可用 `winver` 查看；若低于 18362 请先升级。 |
| **Windows 10** | 早于 1903 / 内部版本 18362                | 否（仅 WSL1） | 需先升级 Windows 才能使用 WSL2 与 Podman。    |

查看本机 Windows 版本与内部版本：

```powershell
winver
```

若为 Windows 10 且内部版本低于 18362，请联系 IT/管理员升级后再使用 WSL2 和 Podman。

---

### 3. 联网环境下启用 WSL（不可控，推荐使用离线部署）

在可联网的 Windows 10/11 上，最简单的方式是：

1. **以管理员身份**打开 **PowerShell**。
2. 执行：

   ```powershell
   wsl --install
   ```
3. 按提示**重启**计算机。
4. 重启后，会完成默认 Linux 发行版（一般为 Ubuntu）的首次配置。

然后再次执行：

```powershell
wsl -l -v
```

确认至少有一个发行版，且状态为 `Running` 或 `Stopped` 均可。

---

### 4. WSL 离线 / 内网部署方案

在**无法直接执行 `wsl --install`** 的环境（企业内网、离线、策略受限等）下，可按以下步骤完成 WSL 的离线部署。

#### 4.1 前置条件

- **Windows 版本**：Windows 10 版本 2004 及以上（内部版本 19041+）或 Windows 11，才能通过 DISM 启用 WSL 并支持 WSL2。
- **架构**：确认目标机为 x64 或 ARM64，与后续下载的安装包架构一致。
- **权限**：启用 Windows 功能、安装 Appx 需**管理员权限**。

#### 4.2 在可联网环境中准备离线资源

在一台可访问外网的 Windows 或可下载文件的机器上，准备以下内容并拷贝到内网/离线环境：

| 资源                           | 说明                                       | 获取方式                                                                                                       |
| ------------------------------ | ------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| **WSL 功能**             | 无需单独下载，通过 DISM 从系统镜像启用     | 见 4.3                                                                                                         |
| **Linux 发行版**         | 例如 Ubuntu 的 `.appx` / `.msixbundle` | 微软应用商店“获取”后从缓存取包，或[Ubuntu WSL Releases](https://github.com/ubuntu/WSL/releases) 等可信源下载    |
| **WSL 内核更新（可选）** | 使用 WSL2 时推荐，提供内核组件             | [Microsoft WSL Releases](https://github.com/microsoft/WSL/releases) 中的 `Microsoft.WSL_<version>.msi` 等安装包 |

**获取 Ubuntu 等发行版离线包的方式示例：**

- 在可联网的 Windows 上打开 [Microsoft Store 中的 Ubuntu 页面](https://apps.microsoft.com/store/detail/ubuntu/9NBLGGH4MSV6)，点击“获取”后，安装包会下载到本地；或按商店“离线安装”相关文档从缓存中定位 `.appx`/`.msixbundle`。
- 或从 Canonical/微软官方推荐渠道（如 [ubuntu/WSL releases](https://github.com/ubuntu/WSL/releases)）下载对应版本的 `.appx`/`.msixbundle`，再通过 U 盘或内网文件共享拷贝到目标机。

微软官方直链：

**Ubuntu 22.04 LTS**

x64: [https://aka.ms/wslubuntu2204]()

ARM64（你如果是 Win11 ARM 必须用这个）：

[https://aka.ms/wslubuntu2204arm64]()

**Ubuntu 24.04 LTS								**

x64: [https://aka.ms/wslubuntu2404]()

ARM64: [https://aka.ms/wslubuntu2404arm64]()

将上述 **Linux 发行版安装包**（以及可选的 WSL 内核更新 MSI）复制到目标机可访问的路径（如 `D:\WSL-Offline`）。

#### 4.3 在目标机上启用 WSL 相关 Windows 功能（离线）

在**目标机**上以**管理员**身份打开 **PowerShell**，依次执行：

```powershell
# 启用“适用于 Linux 的 Windows 子系统”
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# 启用“虚拟机平台”（使用 WSL2 时强烈建议）
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

完成后**重启**计算机。

#### 4.4 安装 WSL 内核更新（可选，推荐用于 WSL2）

若已下载 `Microsoft.WSL_<version>.msi`（或类似名称的 WSL 安装包），在目标机上以管理员身份运行该 MSI，按提示完成安装。若跳过此步，部分 Windows 版本会使用系统自带的 WSL 内核，可能较旧。

#### 4.5 在目标机上安装 Linux 发行版

将准备好的 Linux 发行版 `.appx` / `.msixbundle` 拷贝到目标机后，在**管理员 PowerShell** 中执行（路径请按实际修改）：

```powershell
	# 示例：安装 Ubuntu 的 appxbundle（路径请替换为实际路径）
Add-AppxPackage -Path "D:\WSL-Offline\CanonicalGroupLimited.Ubuntu22.04LTS_xxx.appxbundle"
```

若企业策略禁止通过 `Add-AppxPackage` 安装，可尝试：

- **解压后运行**：将 `.appxbundle` / `.msixbundle` 解压到某目录（可当作 zip 解压），进入该目录，运行其中的 `ubuntu.exe`（或对应发行版的启动器），完成首次注册与初始化。
- 或由 IT 通过组策略/镜像预装该应用包。

#### 4.6 首次启动与验证

1. 从开始菜单或上述安装目录**启动已安装的 Linux 发行版**（如 Ubuntu）。
2. 首次启动会进行初始化（创建用户等），按提示完成。
3. 在 **cmd** 或 **PowerShell** 中执行：

   ```powershell
   wsl -l -v
   ```

   应能看到至少一个发行版，且状态为 `Stopped` 或 `Running`。记下 **VERSION** 列（1 或 2）。
4. **使用本项目（Podman）时必须为 WSL2**。若上一步中 VERSION 为 **1**，需改为 2 后再用：

   - 设置默认版本为 2（之后新装的发行版会使用 WSL2）：
     ```powershell
     wsl --set-default-version 2
     ```
   - 将已有发行版改为 WSL2（将 `Ubuntu` 换成你的发行版名称）：
     ```powershell
     wsl --set-version Ubuntu 2
     ```

   若 VERSION 已是 **2**，可跳过本步。

完成以上步骤后，即可在离线/内网环境中使用 WSL；本项目的 Podman 依赖 WSL 时，可按文档第 6 节继续运行 `scripts\start-for-client.cmd` 或 `scripts\start-for-client.ps1`。

---

### 5. 选择哪种发行版？

对本项目而言，**任意标准 WSL Linux 发行版均可**。推荐：

- **Ubuntu**（LTS 版本如 20.04 / 22.04），兼容性好、使用广泛。

本项目**不依赖**桌面环境，普通的 WSL 服务器式安装即可。

---

### 6. WSL 就绪之后

当 `wsl -l -v` 已显示至少一个已安装的发行版时：

1. 打开新的 **cmd** 或 **PowerShell** 窗口。
2. 进入项目根目录（即包含 `scripts` 文件夹的目录）。
3. 运行启动脚本：

   **在 cmd 中：**

   ```cmd
   scripts\start-for-client.cmd
   ```

   **在 PowerShell 中：**

   ```powershell
   scripts\start-for-client.ps1
   ```

若 Podman 已随项目提供或已加入 `PATH`，脚本将会：

- 启动 Podman Machine（Linux 虚拟机），
- 启动后端与 MariaDB 容器，
- 并在 `http://localhost:8000` 提供后端 API。
