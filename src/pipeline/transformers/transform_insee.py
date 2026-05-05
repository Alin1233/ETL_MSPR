import sys
from pathlib import Path
import pandas as pd
from typing import Dict, List

from mage_ai.settings.repo import get_repo_path

sys.path.insert(0, get_repo_path())

if "transformer" not in globals():
    from mage_ai.data_preparation.decorators import transformer

# We import the functions from flatten_dossier_complet to avoid repeating logic
from src.insee_processing.flatten_dossier_complet import (
    _read_mapping,
    _filter_mapping_to_raw,
    _coerce_types,
    _sanitize_table_name,
)

@transformer
def transform_insee(df: pd.DataFrame, *args, **kwargs) -> Dict[str, pd.DataFrame]:
    """
    Transforms the raw INSEE data in-memory based on the mapping file.
    Returns a dictionary of DataFrames, where keys are table names and 
    values are the corresponding processed DataFrames (Fact tables).
    """
    repo_root = Path(get_repo_path())
    mapping_path = repo_root / "src" / "insee_processing" / "mapping_dossier_complet.csv"
    
    print(f"Reading mapping from {mapping_path}...")
    mapping_df = _read_mapping(mapping_path, sep=";", encoding="utf-8")
    
    raw_columns = set(df.columns)
    
    if "CODGEO" not in raw_columns:
        raise ValueError("Raw data must include CODGEO column.")
        
    mapping_df, _missing = _filter_mapping_to_raw(mapping_df, raw_columns)
    if mapping_df.empty:
        raise ValueError("No mapping rows matched raw data columns.")
        
    print(f"Transforming into {len(mapping_df['target_table'].unique())} target tables...")
    
    output_dfs: Dict[str, pd.DataFrame] = {}
    
    for table_name, table_mapping in mapping_df.groupby("target_table"):
        canonical_order = list(dict.fromkeys(table_mapping["canonical_metric"].tolist()))
        table_frames: List[pd.DataFrame] = []

        for year, year_mapping in table_mapping.groupby("year"):
            source_cols = year_mapping["source_code"].tolist()
            rename_map = dict(zip(source_cols, year_mapping["canonical_metric"]))

            df_out = df[["CODGEO", *source_cols]].copy()
            df_out = df_out.rename(columns=rename_map)
            df_out.insert(1, "annee", int(year))

            data_type_by_metric = dict(
                zip(year_mapping["canonical_metric"], year_mapping["data_type"])
            )
            df_out = _coerce_types(df_out, data_type_by_metric)

            table_frames.append(df_out)

        table_df = pd.concat(table_frames, ignore_index=True)
        table_df = table_df.reindex(columns=["CODGEO", "annee", *canonical_order])
        table_df = table_df.sort_values(by=["CODGEO", "annee"], kind="mergesort")
        
        safe_table_name = _sanitize_table_name(table_name)
        output_dfs[safe_table_name] = table_df
        print(f"   -> Created {safe_table_name} ({len(table_df)} rows, {len(table_df.columns)} cols)")

    print("✅ INSEE Transformation complete.")
    return output_dfs
