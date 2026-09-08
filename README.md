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
| `.env.example` | Same keys, blank values — for colleagues |
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

## 4. Service principal setup

Local Spark reaches OneLake as a service principal. Someone with Fabric admin
rights must confirm:

1. **Tenant setting:** "Service principals can use Fabric APIs" (Admin portal
   → Tenant settings → Developer settings) is enabled, and the SPN is in a
   security group the setting applies to.
2. **Tenant setting:** "Users can access data stored in OneLake with apps
   external to Fabric" (Admin portal → Tenant settings → OneLake settings) is
   enabled. **Local Spark is an "external app."** Without this, every ABFS
   call returns 403 regardless of workspace roles.
3. **Workspace role:** the SPN is a **Member or Contributor** of each target
   workspace. Viewer is not sufficient for data-plane access.

> Tenant settings can be enabled *for a subset of the organization*. "Enabled"
> in the portal looks identical to "enabled but scoped to a group you are not
> in." Check the scoping, not just the toggle.

Azure RBAC roles such as Storage Blob Data Contributor do **not** apply to
OneLake. Only Fabric workspace roles and OneLake data access roles matter.

### Isolating a 403

OneLake returns 403 rather than 404 for paths it will not resolve, so a
permissions error and a wrong path look identical. Test outside Spark:

```powershell
az login --service-principal -u $env:FABRIC_CLIENT_ID -p $env:FABRIC_CLIENT_SECRET --tenant $env:FABRIC_TENANT_ID
$tok = az account get-access-token --resource "https://storage.azure.com" --query accessToken -o tsv

# workspace root
curl.exe -s -o NUL -w "%{http_code}`n" -H "Authorization: Bearer $tok" `
  "https://onelake.dfs.fabric.microsoft.com/<Workspace>?resource=filesystem&recursive=false"

# inside the lakehouse — shows the ACTUAL folder names
curl.exe -s -H "Authorization: Bearer $tok" `
  "https://onelake.dfs.fabric.microsoft.com/<Workspace>?resource=filesystem&recursive=false&directory=<Lakehouse>.Lakehouse/Tables"
```

All levels 403 → tenant-level. Root works but deeper fails → path or item
permission.

---

## 5. Daily workflow

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
    from fabric_local import bootstrap, display, table_path, set_target
    spark = bootstrap()

print("Fabric" if IS_FABRIC else "Local", spark.version)
```

Reading a table:

```python
df = spark.read.format("delta").load(table_path("analysis"))
display(df)
```

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

---

## 7. Troubleshooting

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

## 8. File contents

### `.env` (never commit)

```ini
JAVA_HOME=C:\Program Files\Java\jdk-17
HADOOP_HOME=C:\hadoop
PROJECT_ROOT=C:\files\fabric-dev

FABRIC_TENANT_ID=
FABRIC_CLIENT_ID=
FABRIC_CLIENT_SECRET=

FABRIC_WORKSPACE=Connection_test
FABRIC_LAKEHOUSE=testing_lh
```

### `.gitignore`

```
.env
.venv/
spark-warehouse/
__pycache__/
*.pyc
requirements-lock.txt
```

### `requirements-local.txt`

Pin `pandas` and `numpy` to whatever your Fabric runtime reports — those are
the ones whose behaviour differs across versions.

```
pyspark==3.5.1
delta-spark==3.1.0
python-dotenv==1.0.1
pandas==2.2.3
numpy==1.26.4
itables==2.2.4
ipython==8.26.0
ipykernel
```

### `Makefile`

```makefile
FAB     := C:/tools/fabcli/Scripts/fab.exe
PY      := py -3.11
VENV    := .venv
PYTHON  := $(VENV)/Scripts/python.exe

empty   :=
space   := $(empty) $(empty)

-include .env

WS      ?= $(FABRIC_WORKSPACE)
WSDIR   := $(subst $(space),_,$(WS))
DIR     := ./notebooks/$(WSDIR)
NB      ?=

.PHONY: help login list list-nb pull pull-all push run setup reinstall check freeze

help:
	@echo "Workspace: $(WS)  ->  $(DIR)"
	@echo "Override with WS=\"Other Workspace\""
	@echo ""
	@echo "  make list-nb              - list notebooks in the workspace"
	@echo "  make pull NB=name         - download one notebook"
	@echo "  make pull-all             - download all notebooks"
	@echo "  make push NB=name         - upload one notebook"
	@echo "  make run NB=name          - run notebook on Fabric Spark"
	@echo ""
	@echo "  make setup                - create .venv and install deps"
	@echo "  make reinstall            - reinstall deps into existing .venv"
	@echo "  make check                - show python version, check deps"
	@echo "  make freeze               - write requirements-lock.txt"

login:
	$(FAB) auth login

list:
	$(FAB) ls -l "$(WS).Workspace"

list-nb:
	$(FAB) ls -l "$(WS).Workspace" | findstr /i notebook

pull:
	@if "$(NB)"=="" (echo NB required: make pull NB=name && exit 1)
	@if not exist "$(subst /,\,$(DIR))" mkdir "$(subst /,\,$(DIR))"
	$(FAB) export "$(WS).Workspace/$(NB).Notebook" -o "$(DIR)" --format .ipynb -f

pull-all:
	$(PYTHON) pull_notebooks.py "$(WS)" "$(DIR)"

push:
	@if "$(NB)"=="" (echo NB required: make push NB=name && exit 1)
	$(PYTHON) fix_metadata.py "$(DIR)/$(NB).Notebook/notebook-content.ipynb"
	$(FAB) import "$(WS).Workspace/$(NB).Notebook" -i "$(DIR)/$(NB).Notebook" --format .ipynb -f

run:
	@if "$(NB)"=="" (echo NB required: make run NB=name && exit 1)
	$(FAB) job run "$(WS).Workspace/$(NB).Notebook"

setup:
	@if exist $(VENV) (echo Remove .venv first, or run make reinstall && exit 1)
	$(PY) -m venv $(VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements-local.txt

reinstall:
	$(PYTHON) -m pip install --force-reinstall -r requirements-local.txt

check:
	$(PYTHON) -c "import sys; print(sys.version)"
	$(PYTHON) -m pip check

freeze:
	$(PYTHON) -m pip freeze > requirements-lock.txt
```

> Recipe lines must be indented with **real tabs**. VS Code will convert them
> to spaces unless you add an `.editorconfig` with `[Makefile]` and
> `indent_style = tab`.

### `fabric_local.py`

```python
"""Local stand-ins for the Fabric notebook runtime."""
import os
import sys
from pathlib import Path

from IPython.display import display as _ipy_display
from IPython.core.getipython import get_ipython

ACC = "onelake.dfs.fabric.microsoft.com"
DEFAULT_ROWS = 1000

_ws = None
_lh = None


def bootstrap():
    """Load config, set env vars, build and return a local SparkSession."""
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))

    global _ws, _lh
    _ws = os.environ["FABRIC_WORKSPACE"]
    _lh = os.environ["FABRIC_LAKEHOUSE"]

    root = os.environ["PROJECT_ROOT"]
    if root not in sys.path:
        sys.path.insert(0, root)

    os.environ["PATH"] = os.environ["HADOOP_HOME"] + r"\bin;" + os.environ["PATH"]
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

    verify_env()
    spark = _create_spark()
    register_sql_magic(spark)
    return spark


def set_target(ws: str | None = None, lh: str | None = None):
    """Switch workspace/lakehouse without restarting the kernel."""
    global _ws, _lh
    if ws:
        _ws = ws
    if lh:
        _lh = lh
    print(f"target: {_ws} / {_lh}")


def table_path(name: str, ws: str | None = None, lh: str | None = None) -> str:
    w, l = ws or _ws, lh or _lh
    return f"abfss://{w}@{ACC}/{l}.Lakehouse/Tables/dbo/{name}"


def _create_spark():
    from pyspark.sql import SparkSession
    tenant = os.environ["FABRIC_TENANT_ID"]
    return (
        SparkSession.builder
        .appName("Local-To-Fabric-OneLake")
        .master("local[*]")
        .config("spark.jars.packages",
                "io.delta:delta-spark_2.12:3.1.0,"
                "org.apache.hadoop:hadoop-azure:3.3.4")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.warehouse.dir",
                str(Path(os.environ["PROJECT_ROOT"]) / "spark-warehouse"))
        .config(f"spark.hadoop.fs.azure.account.auth.type.{ACC}", "OAuth")
        .config(f"spark.hadoop.fs.azure.account.oauth.provider.type.{ACC}",
                "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider")
        .config(f"spark.hadoop.fs.azure.account.oauth2.client.id.{ACC}",
                os.environ["FABRIC_CLIENT_ID"])
        .config(f"spark.hadoop.fs.azure.account.oauth2.client.secret.{ACC}",
                os.environ["FABRIC_CLIENT_SECRET"])
        .config(f"spark.hadoop.fs.azure.account.oauth2.client.endpoint.{ACC}",
                f"https://login.microsoftonline.com/{tenant}/oauth2/token")
        .getOrCreate()
    )


def verify_env():
    import importlib.metadata as md
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError(
            f"Python 3.11 required, got {sys.version_info[:2]}. "
            "Select the .venv interpreter as the kernel.")
    for pkg in ("pyspark", "delta-spark", "pandas"):
        try:
            md.version(pkg)
        except md.PackageNotFoundError:
            raise RuntimeError(f"{pkg} missing - run `make setup`")


def display(df, rows: int = DEFAULT_ROWS, summary: bool = False):
    """Fabric-style display() for Spark or pandas DataFrames."""
    if hasattr(df, "toPandas"):
        pdf = df.limit(rows).toPandas()
        note = f"showing up to {rows} rows"
    else:
        pdf = df
        note = f"{len(pdf)} rows"
    _ipy_display(pdf)
    print(f"({note}, {len(pdf.columns)} columns)")
    if summary:
        _ipy_display(pdf.describe(include="all").T)


def register_sql_magic(spark):
    """Enable %%sql cells like in Fabric."""
    ip = get_ipython()
    if ip is None:
        return
    ip.register_magic_function(
        lambda line, cell: display(spark.sql(cell)),
        magic_kind="cell", magic_name="sql")
```

### `fix_metadata.py`

VS Code stamps the notebook with your local kernel on every save, which
overwrites the Fabric language metadata. This restores it before push.

```python
"""Restore Fabric notebook metadata that VS Code overwrites on save."""
import json
import sys
from pathlib import Path

FABRIC_META = {
    "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"},
    "kernel_info": {"name": "synapse_pyspark"},
    "language_info": {"name": "python"},
    "microsoft": {"language": "python", "language_group": "synapse_pyspark"},
}

path = Path(sys.argv[1])
nb = json.loads(path.read_text(encoding="utf-8"))
meta = nb.setdefault("metadata", {})

# Never rewrite a non-PySpark notebook (e.g. SparkR) into PySpark.
current = meta.get("microsoft", {}).get("language_group")
if current and current != "synapse_pyspark":
    print(f"skipping {path.name} - language_group is {current}")
    sys.exit(0)

meta.update(FABRIC_META)
path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"normalized {path.name}")
```

**Verify `FABRIC_META` against your own tenant** before relying on it. Pull a
notebook you set to PySpark in the portal and inspect what Fabric actually
writes:

```powershell
python -c "import json;print(json.dumps(json.load(open(r'notebooks/<WS>/<NB>.Notebook/notebook-content.ipynb'))['metadata'],indent=2))"
```

The exact keys have changed between Fabric releases, and the `dependencies`
block (default lakehouse) lives in the same place — preserve it rather than
overwriting.

### `pull_notebooks.py`

`fab export -a` exports *every* item type — semantic models, reports,
lakehouses, pipelines. This exports notebooks only.

```python
"""Export every notebook (and only notebooks) from a workspace."""
import subprocess
import sys
from pathlib import Path

FAB = r"C:\tools\fabcli\Scripts\fab.exe"

ws, out = sys.argv[1], sys.argv[2]
Path(out).mkdir(parents=True, exist_ok=True)

listing = subprocess.run(
    [FAB, "ls", f"{ws}.Workspace"],
    capture_output=True, text=True, check=True,
).stdout

names = [
    line.split(".Notebook")[0].strip()
    for line in listing.splitlines()
    if ".Notebook" in line
]

if not names:
    sys.exit(f"no notebooks found in {ws}")

for name in names:
    print(f"--- {name}")
    subprocess.run(
        [FAB, "export", f"{ws}.Workspace/{name}.Notebook",
         "-o", out, "--format", ".ipynb", "-f"],
        check=False,
    )

print(f"\n{len(names)} notebooks -> {out}")
```

Check the raw output of `fab ls "<WS>.Workspace"` once before trusting the
parse — header rows or column formatting could break it.

### `.vscode/settings.json`

Stops Pylance from reporting hundreds of errors when parsing R notebooks as
Python:

```json
{
  "python.analysis.exclude": ["**/notebooks/**"]
}
```

---

## 9. Limitations

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

---

## 10. Sharing this setup

Each person should authenticate as themselves rather than sharing a client
secret — a shared SPN gives no audit trail and rotation breaks everyone at
once.

Options, in order of preference:

1. **Per-user `az login`.** `fab auth login` already works this way. For the
   Spark side, a community `AzureCliCredentialTokenProvider` for hadoop-azure
   exists for exactly this case (build the jar once, reference via
   `spark.jars`). Removes the secret from every laptop.
2. **One SPN per person**, with secrets pulled from Key Vault via
   `DefaultAzureCredential` — `.env` then holds only a vault URL.
3. **Shared SPN in `.env`** — simplest, least accountable. Acceptable for a
   sandbox workspace only.

Commit `.env.example`, never `.env`.