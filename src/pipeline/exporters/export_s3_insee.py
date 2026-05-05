import sys
from os import path
from pandas import DataFrame
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.s3 import S3

sys.path.insert(0, get_repo_path())

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

BUCKET_NAME = 'elections-raw'
OBJECT_KEY = 'insee/raw/dossier_complet_2025.parquet'

@data_exporter
def export_data_to_s3(df: DataFrame, **kwargs) -> None:
    """
    Exports the raw INSEE DataFrame to RustFS S3 as Parquet.
    """
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'default'

    print(f"Exporting raw INSEE data ({len(df)} rows) → s3://{BUCKET_NAME}/{OBJECT_KEY}")
    S3.with_config(ConfigFileLoader(config_path, config_profile)).export(
        df,
        BUCKET_NAME,
        OBJECT_KEY,
    )
    print("✅ INSEE raw export done.")
