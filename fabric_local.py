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

    os.environ["JAVA_HOME"] = os.environ["JAVA_HOME"]
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
            raise RuntimeError(f"{pkg} missing — run `make setup`")


def display(df, rows: int = DEFAULT_ROWS, summary: bool = False):
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
    ip = get_ipython()
    if ip is None:
        return
    ip.register_magic_function(
        lambda line, cell: display(spark.sql(cell)),
        magic_kind="cell", magic_name="sql")