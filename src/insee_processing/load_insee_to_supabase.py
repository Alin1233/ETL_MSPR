import argparse
import os
import sys
from pathlib import Path
from typing import Dict

import pandas as pd
from sqlalchemy import create_engine, text

# Add the src/ folder to Python path so we can import from insee_processing
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.insee_processing.flatten_dossier_complet import flatten_dossier_complet_tables

SCHEMA_NAME = "public"

def truncate_pg_columns(df: pd.DataFrame) -> pd.DataFrame:
    new_cols = []
    seen = set()
    for col in df.columns:
        if len(col.encode('utf-8')) > 63:
            short_col = col[:20].strip() + "..." + col[-35:].strip()
            while len(short_col.encode('utf-8')) > 63:
                short_col = short_col[1:]
        else:
            short_col = col
            
        base_short = short_col
        counter = 1
        while short_col in seen:
            suffix = f"_{counter}"
            while len((base_short + suffix).encode('utf-8')) > 63:
                base_short = base_short[:-1]
            short_col = base_short + suffix
            counter += 1
            
        seen.add(short_col)
        new_cols.append(short_col)
        
    df.columns = new_cols
    return df


def load_insee_to_supabase(
    raw_path: Path,
    mapping_path: Path,
    db_url: str,
    limit_rows: int = None
) -> None:
    print(f"1. Transforming INSEE data from {raw_path.name}...")
    # Generate the dictionary of dataframes entirely in memory
    tables: Dict[str, pd.DataFrame] = flatten_dossier_complet_tables(
        raw_path=raw_path,
        mapping_path=mapping_path,
        sep=";",
        encoding="utf-8",
        limit_rows=limit_rows,
        sanitize_table_names=True
    )
    
    print(f"   -> Generated {len(tables)} target tables.")

    print("\n2. Connecting to Supabase...")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        print(f"   -> Fetching dim_geographie from schema '{SCHEMA_NAME}'...")
        dim_geo_df = pd.read_sql(
            f"SELECT geo_sk, code_commune FROM {SCHEMA_NAME}.dim_geographie", 
            conn
        )
        print(f"   -> Loaded {len(dim_geo_df)} communes from Supabase.")

        pk_statements = []
        fk_statements = []
        # Function truncate_pg_columns was here, moved to top level
        print("\n3. Processing and Exporting Fact Tables...")
        for raw_table_name, df in tables.items():
            fact_table_name = f"fact_insee_{raw_table_name}"
            pk_column = f"fact_{raw_table_name}_id"
            
            print(f"   [{fact_table_name}] Merging with geography...")
            # Inner join to map CODGEO to geo_sk and filter out unknown communes
            merged_df = df.merge(
                dim_geo_df, 
                left_on='CODGEO', 
                right_on='code_commune', 
                how='inner'
            )
            
            # Drop the string codes, we only want the surrogate key
            merged_df = merged_df.drop(columns=['CODGEO', 'code_commune'])
            
            # Add Primary Key column deterministically
            merged_df = merged_df.sort_values(by=['geo_sk', 'annee'])
            
            # Fix fragmentation warning by re-assigning df instead of insert
            pk_series = range(1, len(merged_df) + 1)
            merged_df = pd.concat([pd.Series(pk_series, name=pk_column, index=merged_df.index), merged_df], axis=1)
            
            # Shorten column names for Postgres limits
            merged_df = truncate_pg_columns(merged_df)
            
            print(f"   [{fact_table_name}] Pushing {len(merged_df)} rows to Supabase...")
            merged_df.to_sql(
                fact_table_name,
                con=conn,
                schema=SCHEMA_NAME,
                if_exists='replace',
                index=False,
            )
            
            # Prepare SQL constraints for later
            pk_statements.append(text(f"ALTER TABLE {SCHEMA_NAME}.{fact_table_name} ADD PRIMARY KEY ({pk_column});"))
            fk_statements.append(text(f"""
                ALTER TABLE {SCHEMA_NAME}.{fact_table_name}
                ADD CONSTRAINT fk_{raw_table_name}_geo
                FOREIGN KEY (geo_sk) REFERENCES {SCHEMA_NAME}.dim_geographie(geo_sk);
            """))

        print("\n4. Applying Primary Key and Foreign Key constraints...")
        
        # Check if dim_geographie has a Primary Key
        pk_check_query = text(f"""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_schema = '{SCHEMA_NAME}' 
              AND table_name = 'dim_geographie' 
              AND constraint_type = 'PRIMARY KEY';
        """)
        has_pk = conn.execute(pk_check_query).fetchone()
        if not has_pk:
            print("   -> ⚠️ dim_geographie is missing a Primary Key. Fixing it now...")
            conn.execute(text(f"ALTER TABLE {SCHEMA_NAME}.dim_geographie ADD PRIMARY KEY (geo_sk);"))
            conn.commit()

        # Since we use `if_exists="replace"`, we must recreate constraints
        for stmt in pk_statements:
            conn.execute(stmt)
        print("   -> Primary Keys applied.")
        
        for stmt in fk_statements:
            conn.execute(stmt)
        print("   -> Foreign Keys applied.")
        
        conn.commit()

    print("\n🎉 INSEE Data successfully processed and pushed to Supabase!")

# --- SUPABASE CONNECTION CONFIGURATION ---
POSTGRES_USER = "postgres.skcqsmtdkxpmflvdbjwb"
POSTGRES_PASSWORD = "atFUMf5Y497DWqfX"
POSTGRES_HOST = "aws-1-eu-west-3.pooler.supabase.com"
POSTGRES_PORT = 6543
POSTGRES_DBNAME = "postgres"

def get_db_url():
    return f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DBNAME}"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process INSEE data and push directly to Supabase as Fact tables.")
    parser.add_argument("--raw", type=Path, default=Path("data/dossier_complet_2025/dossier_complet_2025.csv"), help="Path to raw dossier_complet_2025.csv")
    parser.add_argument("--mapping", type=Path, default=Path("src/insee_processing/mapping_dossier_complet.csv"), help="Path to mapping CSV")
    parser.add_argument("--limit-rows", type=int, default=None, help="Optional row limit for testing")
    
    args = parser.parse_args()
    
    if not args.raw.exists():
        print(f"❌ Error: Raw file not found at {args.raw}", file=sys.stderr)
        sys.exit(1)
        
    db_url = get_db_url()
        
    load_insee_to_supabase(
        raw_path=args.raw,
        mapping_path=args.mapping,
        db_url=db_url,
        limit_rows=args.limit_rows
    )
