## Windows 环境变量生效方式速查（以 `BUNDLED_RUNTIME_ROOT` 为例）

本项目中的脚本（例如 `scripts/start-for-client.ps1` / `scripts/start-for-client.cmd`）会读取环境变量 `BUNDLED_RUNTIME_ROOT`，用于指定“打包好的运行时目录”（如 Podman / Docker 及相关工具所在的位置）。下面总结在 Windows 下几种常见的设置方式，以及它们生效范围的区别。

---

### 1. 临时设置：只在当前 `cmd` 窗口中生效

- **作用范围**：仅当前命令行会话（这个窗口），关闭窗口后失效。
- **适用于**：一次性测试、临时修改。

```cmd
set BUNDLED_RUNTIME_ROOT=D:\my-offline-runtime
scripts\start-for-client.cmd
```

说明：
- 先用 `set` 在当前窗口中设置环境变量；
- 随后运行脚本时，脚本就能读到这个变量；
- 退出或关闭该 `cmd` 窗口后，变量不再存在。

也可以把设置和执行合在一行：

```cmd
set BUNDLED_RUNTIME_ROOT=D:\my-offline-runtime && scripts\start-for-client.cmd
```

---

### 2. 在 PowerShell 中临时设置

- **作用范围**：仅当前 PowerShell 会话（这个标签/窗口）。

```powershell
$env:BUNDLED_RUNTIME_ROOT = "D:\my-offline-runtime"
scripts\start-for-client.ps1
```

关闭该 PowerShell 会话后，变量失效。

---

### 3. 永久设置：通过“环境变量”界面配置

- **作用范围**：
  - “用户变量”：当前用户下所有新开的 `cmd` / PowerShell / 其他进程。
  - “系统变量”：整台机器的所有用户和新进程。
- **适用于**：希望长期固定使用某个 runtime 目录的场景。

操作步骤（Windows 图形界面）：

1. 打开“系统属性”：
   - 方法之一：在“此电脑”/“这台电脑”上右键 → `属性` → `高级系统设置`。
2. 点击下方的 `环境变量(N)...`。
3. 在“用户变量”或“系统变量”部分点击“新建(N)...”：
   - 变量名：`BUNDLED_RUNTIME_ROOT`
   - 变量值：例如 `D:\my-offline-runtime`
4. 保存后，**重新打开** `cmd` / PowerShell 窗口，再运行脚本。

---

### 4. 不设置时的默认行为

在 `start-for-client.ps1` 中，runtime 根目录的选择逻辑大致如下：

```powershell
# 伪代码说明逻辑
if ($env:BUNDLED_RUNTIME_ROOT) {
    $RuntimeRoot = $env:BUNDLED_RUNTIME_ROOT
} else {
    $RuntimeRoot = Join-Path $ProjectRoot "runtime"
}
```

也就是说：

- **如果设置了 `BUNDLED_RUNTIME_ROOT`**：脚本优先使用你指定的目录。
- **如果没有设置**：脚本回退到项目自身目录下的 `runtime\` 作为默认运行时目录。

---

### 5. 快捷自检：确认变量是否生效

在 `cmd` 中：

```cmd
echo %BUNDLED_RUNTIME_ROOT%
```

在 PowerShell 中：

```powershell
echo $env:BUNDLED_RUNTIME_ROOT
```

如果能正确显示你设置的路径，说明环境变量已在当前会话中生效，脚本也就能读到这个值。

