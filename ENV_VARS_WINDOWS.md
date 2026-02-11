## Windows environment variables quick reference (using `BUNDLED_RUNTIME_ROOT` as an example)

Scripts in this project (e.g. `scripts/start-for-client.ps1` / `scripts/start-for-client.cmd`) read the environment variable `BUNDLED_RUNTIME_ROOT` to specify the bundled runtime directory (where Podman / Docker and related tools are located). Below is a summary of common ways to set it on Windows and how their scope differs.

---

### 1. Temporary: only in the current `cmd` window

- **Scope**: Current command-line session only; the variable is lost when you close the window.
- **Use when**: One-off tests or temporary overrides.

```cmd
set BUNDLED_RUNTIME_ROOT=D:\my-offline-runtime
scripts\start-for-client.cmd
```

Notes:
- Use `set` to define the variable in the current window.
- The script will then see this value when you run it.
- After you exit or close that `cmd` window, the variable no longer exists.

You can also set and run in one line:

```cmd
set BUNDLED_RUNTIME_ROOT=D:\my-offline-runtime && scripts\start-for-client.cmd
```

---

### 2. Temporary in PowerShell

- **Scope**: Current PowerShell session (this tab/window) only.

```powershell
$env:BUNDLED_RUNTIME_ROOT = "D:\my-offline-runtime"
scripts\start-for-client.ps1
```

After you close that PowerShell session, the variable is gone.

---

### 3. Permanent: via the Environment Variables UI

- **Scope**:
  - **User variables**: All new `cmd` / PowerShell / other processes for the current user.
  - **System variables**: All users and new processes on the machine.
- **Use when**: You want to permanently use a specific runtime directory.

Steps (Windows GUI):

1. Open **System properties**:
   - One way: Right-click **This PC** → **Properties** → **Advanced system settings**.
2. Click **Environment Variables...** at the bottom.
3. Under **User variables** or **System variables**, click **New...**:
   - Variable name: `BUNDLED_RUNTIME_ROOT`
   - Variable value: e.g. `D:\my-offline-runtime`
4. After saving, **open a new** `cmd` or PowerShell window, then run the script.

---

### 4. Default when not set

In `start-for-client.ps1`, the runtime root is chosen roughly as follows:

```powershell
# Pseudocode for the logic
if ($env:BUNDLED_RUNTIME_ROOT) {
    $RuntimeRoot = $env:BUNDLED_RUNTIME_ROOT
} else {
    $RuntimeRoot = Join-Path $ProjectRoot "runtime"
}
```

So:

- **If `BUNDLED_RUNTIME_ROOT` is set**: The script uses your specified directory.
- **If not set**: The script falls back to the project’s own `runtime\` directory as the default runtime root.

---

### 5. Quick check: confirm the variable is in effect

In `cmd`:

```cmd
echo %BUNDLED_RUNTIME_ROOT%
```

In PowerShell:

```powershell
echo $env:BUNDLED_RUNTIME_ROOT
```

If the path you set is printed, the variable is in effect in the current session and the script will read it.
