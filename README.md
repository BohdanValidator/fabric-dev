# Local Fabric Development Setup

Develop Fabric notebooks locally in VS Code, read and write OneLake Delta
tables from a local Spark session, and sync notebooks between your machine
and Fabric workspaces — without Git integration.

**Platform:** Windows. Times are approximate for a first-time setup: ~45 min.

---

## 1. Prerequisites

Install these before anything else. Versions matter — the combinations below
are the ones known to work together.

### 1.1 JDK 17

Spark 3.5 runs on Java 8, 11, or 17 only. **Java 21+ will not work.**

Download Temurin JDK 17 (or Oracle JDK 17). Then set `JAVA_HOME` to the JDK
root — the folder containing `bin` and `lib`, *not* `bin` itself, with no
trailing backslash:

```powershell
[Environment]::SetEnvironmentVariable("JAVA_HOME", "C:\Program Files\Java\jdk-17", "User")
```

> **Having `java` on PATH is not enough.** Spark's Windows launcher checks
> `JAVA_HOME` first and fails with `JAVA_GATEWAY_EXITED` if it is unset.

Find your actual install path with `Get-ChildItem "C:\Program Files\Java"`.
Confirm it is a JDK, not a JRE:

```powershell
Test-Path "C:\Program Files\Java\jdk-17\bin\javac.exe"   # must be True
```

### 1.2 Python 3.11

**Do not use Python 3.14.** Many packages have no wheels for it yet, and
several will try (and fail) to compile from source.

Install Python 3.11 from python.org. Verify with `py -3.11 --version`.

### 1.3 Hadoop native binaries (winutils)

Hadoop needs `winutils.exe` and `hadoop.dll` on Windows. Without them, Spark
fails at `Shell.checkHadoopHomeInner` as soon as `hadoop-azure` loads.

1. Download the `hadoop-3.3.x/bin` folder contents from the
   [cdarlint/winutils](https://github.com/cdarlint/winutils) repository
   (3.3.5 or 3.3.6 both work with hadoop-azure 3.3.4).
2. Put `winutils.exe` and `hadoop.dll` in `C:\hadoop\bin`.
3. Set the environment variable and PATH entry:

```powershell
[Environment]::SetEnvironmentVariable("HADOOP_HOME", "C:\hadoop", "User")
```

Add `C:\hadoop\bin` to your user PATH via System Properties → Environment
Variables. `hadoop.dll` must be loadable from PATH, not merely present on disk.

Verify:

```powershell
C:\hadoop\bin\winutils.exe systeminfo
```

It should print a row of comma-separated numbers. If it errors, install the
**Microsoft Visual C++ 2015-2022 Redistributable (x64)**.

### 1.4 GNU Make

```powershell
winget install ezwinports.make
```

Or `choco install make`. Verify with `make --version`.

### 1.5 Fabric CLI

Install it in its **own** virtual environment so its dependencies can never
conflict with your project's:

```powershell
py -3.11 -m venv C:\tools\fabcli
C:\tools\fabcli\Scripts\python.exe -m pip install --upgrade pip
C:\tools\fabcli\Scripts\pip.exe install ms-fabric-cli
C:\tools\fabcli\Scripts\fab.exe --version
```

Optionally add `C:\tools\fabcli\Scripts` to PATH. The Makefile calls the full
path, so this is not required.

### 1.6 VS Code extensions

- **Python** and **Jupyter** (required)
- **Fabric Data Engineering** (optional — useful for running notebooks on
  remote Fabric Spark compute and for its conflict-aware publish flow)

---

## 2. Restart everything

After setting `JAVA_HOME` and `HADOOP_HOME`, **close VS Code completely** —
every window, and check the system tray. The kernel inherits its environment
from the VS Code process, which captured it at launch. Restarting the kernel
or reopening a notebook is *not* sufficient.

If variables still do not appear after a full restart, sign out of Windows
and back in.

---

## 3. Project setup

### 3.1 Create the project

```powershell
mkdir C:\files\fabric-dev
cd C:\files\fabric-dev
mkdir notebooks
```

### 3.2 Files to create

The project needs these files (contents in section 8):

| File | Purpose |
|---|---|
| `.env` | Your machine paths, credentials, target workspace |
| `.gitignore` | Keeps secrets and build output out of Git |
| `requirements-local.txt` | Python dependencies |
| `Makefile` | Sync and environment commands |
| `fabric_local.py` | Local stand-ins for Fabric runtime helpers |
| `fix_metadata.py` | Restores Fabric notebook metadata before push |
| `pull_notebooks.py` | Exports notebooks only (not every item type) |

### 3.3 Build the virtual environment

```powershell
make setup
```

Then in VS Code, select `.venv\Scripts\python.exe` as the notebook kernel
(kernel selector, top right of the notebook editor).

> **Do not run `make setup` from inside an activated venv** — Windows locks
> `python.exe` and the recreate fails with a permission error. Run
> `deactivate` first, or use `make reinstall` which does not touch the
> interpreter.

### 3.4 Authenticate the CLI

```powershell
make login
make list-nb
```

`fab` authenticates as **you**, interactively — not as the service principal
in `.env`. If a workspace does not appear, it is your own account's access.

---

## 4. Daily workflow

```powershell
# see what is in a workspace
make list-nb
make list-nb WS="Suntory Gold"

# pull
make pull NB=automation_test
make pull-all                      # notebooks only, current workspace

# edit and run locally in VS Code, then
make push NB=automation_test

# or run on Fabric compute
make run NB=automation_test
```

### Switching workspaces

Edit `FABRIC_WORKSPACE` and `FABRIC_LAKEHOUSE` in `.env`. This drives both
the Makefile (which folder notebooks sync to) and the notebook (which
lakehouse `table_path()` points at).

**Restart the kernel** after changing `.env` — `load_dotenv` does not override
variables already loaded into the process.

To switch data targets without restarting:

```python
set_target(ws="ValidatorsDevelopment", lh="ValiLakehouse")
```

Override per command without touching `.env`:

```powershell
make pull-all WS="Suntory Gold"
```

### Notebook bootstrap cell

Every notebook starts with this cell. It is identical in every notebook and
works unchanged in both environments:

```python
try:
    import notebookutils
    IS_FABRIC = True
except ImportError:
    IS_FABRIC = False

if not IS_FABRIC:
    import sys
    sys.path.insert(0, r"C:\files\fabric-dev")
    from fabric_local import bootstrap, display, table_path, set_target, storage_options
    spark = bootstrap()
else:
    def storage_options(): return {}

print("Fabric" if IS_FABRIC else "Local", spark.version)
```

Reading a table:

```python
df = spark.read.format("delta").load(table_path("analysis"))
display(df)
```
<!-- 
---

## 6. Critical gotchas

These cost real time to diagnose. Read them before troubleshooting.

### Hadoop config keys need the `spark.hadoop.` prefix

Spark only copies keys beginning with `spark.hadoop.` into the Hadoop
`Configuration` (stripping the prefix). A bare `fs.azure.*` key on the builder
sits in SparkConf and is never seen by ABFS.

**Symptom:** `Failure to initialize configuration` from `SimpleKeyProvider` —
ABFS fell back to SharedKey auth because it never saw your OAuth settings.

### The provider class is `azurebfs`, not `azureblob`

```
org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider
```

### `az login` is not used by `ClientCredsTokenProvider`

That provider is service-principal only and requires
`fs.azure.account.oauth2.client.id`, `.client.secret`, and `.client.endpoint`.
There is no stock hadoop-azure provider that picks up an Azure CLI session.

### A stale SparkContext silently ignores your config

`getOrCreate()` returns an existing context and **drops every `.config()` you
passed**. `spark.jars.packages` is a launch-time setting and cannot be applied
to a running JVM at all.

Diagnose:

```python
print(spark.conf.get("spark.jars.packages", "NOT SET"))              # session config
print(spark.sparkContext.getConf().get("spark.sql.extensions", "NOT SET"))  # live JVM
```

If the first shows a value and the second says `NOT SET`, you are on a stale
context. **Restart the kernel** and run the bootstrap cell first. Any cell that
touches `spark` before the bootstrap creates a default context and puts you
back here.

### Filesystem and DeltaLog caching

Hadoop caches `FileSystem` instances per scheme+authority for the JVM's
lifetime; Delta caches `DeltaLog` per path. After any auth config change,
restart the kernel — re-running the builder does not invalidate either cache.

### Schema-enabled vs. plain lakehouse paths

- Schema-enabled: `Tables/dbo/<table>`
- Plain: `Tables/<table>`

Getting this wrong returns **403, not 404**. Right-click the table in the
Fabric portal and copy the ABFS path rather than guessing.

### VS Code environment inheritance

The notebook kernel inherits the environment from the VS Code process at
launch. New or changed environment variables require a **full VS Code
restart**, not a kernel restart.

--- -->

## 5. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `JAVA_GATEWAY_EXITED` | `JAVA_HOME` unset, wrong Java version, or blocked Ivy resolution | Section 1.1; test a bare session with no `spark.jars.packages` |
| `ClassNotFoundException` for Delta | Stale SparkContext dropped your config | Restart kernel, bootstrap cell first |
| `Shell.checkHadoopHomeInner` | winutils missing or `HADOOP_HOME` not visible to the JVM | Section 1.3, then full VS Code restart |
| `Failure to initialize configuration` | Missing `spark.hadoop.` prefix or `auth.type` | Section 6 |
| `403 Forbidden` on ABFS | Tenant setting, workspace role, or wrong path | Section 4 |
| Session hangs on create | Kernel is not the venv, or Python/worker mismatch | Check `sys.executable`; kill orphan `java` processes |
| Kernel never connects | `ipykernel` missing, or VS Code webview broken | `pip install ipykernel`; Developer: Reload Window |
| "Could not register service worker" | VS Code webview cache corrupt | Reload window; clear `%APPDATA%\Code\Cache` and `Service Worker` |
| `fab` not found | Not on PATH | Use the full path, or add `C:\tools\fabcli\Scripts` and restart |
| `export: [InvalidPath]` | Output directory does not exist; `fab` will not create it | `mkdir` first (the Makefile does this) |
| `Permission denied: python.exe` | Running `make setup` inside the activated venv | `deactivate`, or use `make reinstall` |
| pip builds pyyaml from source and fails | Running under Python 3.14 | Use `py -3.11` |

### Bare-session test

When Spark will not start, isolate it from dependency resolution by running
this in a terminal (where JVM stderr is visible, unlike in Jupyter):

```powershell
python -c "from pyspark.sql import SparkSession; s=SparkSession.builder.master('local[*]').getOrCreate(); print(s.range(3).count())"
```

Prints `3` → Java and PySpark are fine; the problem is jars, config, or the
kernel. Hangs or errors → environment.

### Harmless errors

- `WARN NativeCodeLoader: Unable to load native-hadoop library` — normal.
- `WARNING: Using incubator modules: jdk.incubator.vector` — normal on Java 17+.
- `ERROR ShutdownHookManager: Exception while deleting Spark temp dir` — occurs
  after your result, on exit. Cosmetic.

---



## 6. Limitations

**Local Spark is not a Fabric emulator.** There is no `notebookutils`, no
default lakehouse mount, no `%%sparkr`/`%%sql` language switching at the
notebook level, and no chart-builder UI in `display()`. Write transformations
as plain functions taking and returning DataFrames, and keep all Fabric-only
API calls behind the `IS_FABRIC` guard.

**Version alignment matters.** Check the Spark and Delta versions of your
Fabric runtime in workspace settings and match them locally. A table written
locally under a newer Delta protocol version can be **unreadable** by an
older Fabric runtime.

**The published Fabric conda environment cannot be reproduced locally.** Much
of it is Linux-only (`xorg-*`, `alsa-lib`, `dbus`) and it is conda, not pip.
Install only what you actually import.

**R notebooks cannot run locally** without a full R + SparkR stack. Edit them
as text and run them via `make run` or in the portal. `fix_metadata.py` skips
them.

**`fab import` overwrites unconditionally.** There is no conflict detection —
if a colleague edited a notebook in the portal since your pull, your push
silently discards their change. Push one notebook at a time, and only ones
you actually edited. Run `git init` and commit right after pulling; it is the
only recovery path.

