## WSL setup guide for Windows (for Podman)

This project uses **Podman on Windows**, which in turn relies on **WSL (Windows Subsystem for Linux)** and at least one Linux distribution (for example, Ubuntu).

If the script detects that WSL is not ready, it will stop starting Podman and show a message pointing you to this file.

---

### 1. Check whether WSL is already installed

Open **PowerShell** or **cmd** as a normal user and run:

```powershell
wsl -l -v
```

If you see at least one distribution in the list (for example `Ubuntu`), WSL is already installed and usable.

If you see a message like **“No installed distributions”** or an error, follow the steps below.

---

### 2. WSL2 support by Windows version

WSL2 is available only on certain Windows versions. Summary:

| Windows edition | Minimum version / build | WSL2 supported | Notes |
|-----------------|-------------------------|----------------|-------|
| **Windows 11**  | Any (all builds)        | Yes            | `wsl --install` installs WSL2 by default. |
| **Windows 10**  | Version 1903, Build **18362** or later | Yes | Use `winver` to check; upgrade if build &lt; 18362. |
| **Windows 10**  | Older than 1903 / Build 18362 | No (WSL1 only) | Upgrade Windows to use WSL2 and Podman. |

Check your Windows version and build:

```powershell
winver
```

If you are on Windows 10 and the build is lower than 18362, ask your IT / admin to upgrade Windows before using WSL2 and Podman.

---

### 3. Enable WSL feature (online)

On Windows 10/11 with Internet access, the simplest way is:

1. Open **PowerShell as Administrator**.
2. Run:

   ```powershell
   wsl --install
   ```

3. Reboot when Windows asks you to.
4. After reboot, a Linux distribution (by default Ubuntu) will finish its first‑time setup.

Then run again:

```powershell
wsl -l -v
```

to confirm there is at least one distro and its state is `Running` or `Stopped` (both are fine).

---

### 4. Enable WSL feature (offline / controlled environment)

In some enterprise or offline scenarios, you may not be able to use `wsl --install` directly. In that case:

1. Ask your IT / image maintainer to:
   - Turn on **Windows Subsystem for Linux** feature.
   - Optionally also turn on **Virtual Machine Platform** (recommended).
2. Obtain an offline `.appx` / `.msixbundle` package of a Linux distro (for example Ubuntu) from a trusted source.
3. Install the distro package on the target machine.
4. Launch the distro once so that it can complete its first‑time setup.

After that, `wsl -l -v` should list at least one installed distribution.

---

### 5. Which distro to choose?

For this project, **any standard WSL Linux distribution is fine**. We recommend:

- **Ubuntu** (LTS versions such as 20.04 / 22.04) because it is well supported and widely tested.

The project does **not** depend on any desktop components; a normal WSL server‑style installation is enough.

---

### 6. After WSL is ready

Once `wsl -l -v` shows at least one installed distro:

1. Open a new **cmd** or **PowerShell** window.
2. Go to the project root directory (the folder that contains the `scripts` folder).
3. Run the start script:

   **From cmd:**

   ```cmd
   scripts\start-for-client.cmd
   ```

   **From PowerShell:**

   ```powershell
   scripts\start-for-client.ps1
   ```

If Podman itself is bundled or available on `PATH`, the script will then:

- Start the Podman Machine (Linux VM),
- Start the backend and MariaDB containers,
- And expose the backend API on `http://localhost:8000`.

