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
    base_path = Path(get_repo_path()) / "raw_data"
    source_path = base_path / "dossier_complet_2025.csv"

    if not source_path.exists():
        raise FileNotFoundError(f"Source introuvable: {source_path}")

    print(f"Reading raw INSEE data from {source_path}...")
    
    # Read mapping to find which columns we actually need
    mapping_path = Path(get_repo_path()) / "src" / "insee_processing" / "mapping_dossier_complet.csv"
    mapping_df = pd.read_csv(mapping_path, sep=";", encoding="utf-8", dtype=str)
    
    # We always need CODGEO, plus any source_code mentioned in the mapping
    required_columns = {"CODGEO"} | set(mapping_df["source_code"].dropna().str.strip())
    
    # Read only the header of the raw file to see which required columns actually exist
    raw_columns = set(pd.read_csv(source_path, sep=";", encoding=kwargs.get("encoding", DEFAULT_ENCODING), nrows=0).columns)
    usecols = list(required_columns.intersection(raw_columns))
    
    print(f"Optimizing extract: Loading only {len(usecols)} columns instead of 1900+...")

    # We read everything as string to prevent mixed types warnings
    df = pd.read_csv(
        source_path,
        sep=";",
        encoding=kwargs.get("encoding", DEFAULT_ENCODING),
        dtype=str,
        usecols=usecols,
        low_memory=False
    )
    
    print(f"✅ Loaded {len(df)} rows and {len(df.columns)} columns.")
    # We return a dictionary to prevent Mage AI from attempting to 
    # compute UI statistics on 1900+ columns, which causes it to hang/crash.
    return {"insee_raw": df}
