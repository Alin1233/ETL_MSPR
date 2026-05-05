import sys
from pathlib import Path
import pandas as pd
from mage_ai.settings.repo import get_repo_path

sys.path.insert(0, get_repo_path())

if "data_loader" not in globals():
    from mage_ai.data_preparation.decorators import data_loader

DEFAULT_ENCODING = "utf-8"

@data_loader
def load_insee_brut(*args, **kwargs):
    """
    Loads the raw dossier_complet_2025.csv into a pandas DataFrame.
    """
    base_path = Path(get_repo_path()) / "data" / "dossier_complet_2025"
    source_path = base_path / "dossier_complet_2025.csv"

    if not source_path.exists():
        raise FileNotFoundError(f"Source introuvable: {source_path}")

    print(f"Reading raw INSEE data from {source_path}...")
    
    # We read everything as string to prevent mixed types warnings, 
    # the types will be coerced during the transform block according to the mapping.
    df = pd.read_csv(
        source_path,
        sep=";",
        encoding=kwargs.get("encoding", DEFAULT_ENCODING),
        dtype=str,
        low_memory=False
    )
    
    print(f"✅ Loaded {len(df)} rows and {len(df.columns)} columns.")
    return df
