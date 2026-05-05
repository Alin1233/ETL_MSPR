import sys
from os import path
import pandas as pd
from typing import Dict

from mage_ai.settings.repo import get_repo_path
from mage_ai.io.config import ConfigFileLoader
from mage_ai.io.postgres import Postgres

sys.path.insert(0, get_repo_path())

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

SCHEMA_NAME = 'public'

@data_exporter
def export_data_to_postgres(dfs: Dict[str, pd.DataFrame], **kwargs) -> None:
    """
    Exports the dictionary of INSEE DataFrames to Supabase as Fact tables.
    Each table is linked to dim_geographie using the geo_sk surrogate key.
    """
    config_path = path.join(get_repo_path(), 'io_config.yaml')
    config_profile = 'default'

    print("1. Connecting to Supabase to fetch dim_geographie...")
    with Postgres.with_config(ConfigFileLoader(config_path, config_profile)) as loader:
        # Load the geographic mapping
        dim_geo_df = loader.load(f"SELECT geo_sk, code_commune FROM {SCHEMA_NAME}.dim_geographie")
        print(f"   Loaded {len(dim_geo_df)} communes from dim_geographie.")

        # Prepare for FK constraints later
        fk_statements = []
        pk_statements = []

        print("2. Processing and exporting each INSEE table...")
        for raw_table_name, df in dfs.items():
            # Standardize table name
            fact_table_name = f"fact_insee_{raw_table_name}"
            pk_column = f"fact_{raw_table_name}_id"
            
            print(f"   Preparing {fact_table_name} ({len(df)} rows)...")

            # Inner join with dim_geographie to get geo_sk
            # Using inner join ensures we only keep rows for known communes
            merged_df = df.merge(
                dim_geo_df, 
                left_on='CODGEO', 
                right_on='code_commune', 
                how='inner'
            )
            
            # Drop the string commune codes, keep the surrogate key
            merged_df = merged_df.drop(columns=['CODGEO', 'code_commune'])
            
            # Add Primary Key column
            # We sort to ensure deterministic ID assignment
            merged_df = merged_df.sort_values(by=['geo_sk', 'annee'])
            merged_df.insert(0, pk_column, range(1, len(merged_df) + 1))
            
            print(f"   Exporting {fact_table_name} to Supabase...")
            loader.export(
                merged_df,
                SCHEMA_NAME,
                fact_table_name,
                index=False,
                if_exists='replace',
                drop_table_on_replace=True,
            )
            
            # Prepare constraint queries
            pk_statements.append(f"ALTER TABLE {SCHEMA_NAME}.{fact_table_name} ADD PRIMARY KEY ({pk_column});")
            fk_statements.append(f"""
                ALTER TABLE {SCHEMA_NAME}.{fact_table_name}
                ADD CONSTRAINT fk_{raw_table_name}_geo
                FOREIGN KEY (geo_sk) REFERENCES {SCHEMA_NAME}.dim_geographie(geo_sk);
            """)

        print("3. Creating Primary Key constraints...")
        for stmt in pk_statements:
            loader.execute(stmt)
            print("   PK constraint applied.")

        print("4. Creating Foreign Key constraints...")
        for stmt in fk_statements:
            loader.execute(stmt)
            print("   FK constraint applied.")

    print("🎉 INSEE Pipeline Complete! Fact tables exported to Supabase.")
