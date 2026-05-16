import sys
from os import path
from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.s3 import S3

sys.path.insert(0, get_repo_path())

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader

BUCKET_NAME = 'elections-raw'
OBJECT_KEY = 'insee/raw/dossier_complet_2025.parquet'

@data_loader
def load_from_s3(*args, **kwargs):
    """
    Loads the raw INSEE Parquet from RustFS S3.
    """
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'default'

    print(f"Loading s3://{BUCKET_NAME}/{OBJECT_KEY}")
    df = S3.with_config(ConfigFileLoader(config_path, config_profile)).load(
        BUCKET_NAME,
        OBJECT_KEY,
    )
    print(f"✅ INSEE loaded: {len(df)} rows")
    return {"insee_raw": df}
