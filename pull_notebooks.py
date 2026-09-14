"""Export every notebook (and only notebooks) from a workspace."""
import subprocess
import sys
from pathlib import Path

FAB = r"C:\tools\fabcli\Scripts\fab.exe"

ws, out = sys.argv[1], sys.argv[2]
Path(out).mkdir(parents=True, exist_ok=True)

listing = subprocess.run([FAB, "ls", f"{ws}.Workspace"],
    capture_output=True, text=True, check=True
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