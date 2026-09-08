import json, sys
from pathlib import Path

FABRIC_META = {
    "kernelspec": {"name": "synapse_pyspark", "display_name": "Synapse PySpark"},
    "kernel_info": {"name": "synapse_pyspark"},
    "language_info": {"name": "python"},
    "microsoft": {"language": "python", "language_group": "synapse_pyspark"},
}

path = Path(sys.argv[1])
nb = json.loads(path.read_text(encoding="utf-8"))
nb.setdefault("metadata", {}).update(FABRIC_META)
path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"normalized {path}")