### Example
Les données sont dans le dossier /data, et les sorties dans /processed_data

#### Folder (2008 & 2014 & 2020 & 2026)
```powershell
python -m src.preprocessing.run_pipeline --input data --format csv --output processed_data/elections_flat.csv
```

#### Single file #1
```powershell
python -m src.preprocessing.run_pipeline --input data\MN14_Bvot_T1T2.txt --format parquet --output processed_data/mn14_flat.parquet
```

#### Single file #2
```powershell
python -m src.preprocessing.run_pipeline --input data --year 2008,2014 --format csv
python -m src.preprocessing.run_pipeline --input data --year all --format parquet
```

#### Options
- `--input` / `--source-dir` : fichier ou dossier d’entrée
- `--output` : chemin exact du fichier de sortie
- `--format` : `csv` ou `parquet`
- `--encoding` : encodage des sources (2008/2014/2020), par défaut `latin-1` (`2026` est forcé en `utf-8`)
- `--year` / `--years` : `all` par défaut, ou liste séparée par des virgules
- `--strict` : échoue si un jeu de données attendu manque dans le dossier

### Outputs
Le format final contient 16 colonnes harmonisées :

- métadonnées d’élection : `annee_election`, `tour`
- géographie : `code_departement`, `libelle_departement`, `code_commune`, `libelle_commune`
- agrégats commune : `inscrits`, `abstentions`, `votants`, `blancs_nuls`, `exprimes`
- ligne résultat : `code_nuance`, `nom`, `prenom`, `liste`, `voix`

### Tables de fait & dimensions
Le fichier `processed_data/elections_flat.csv` peut être transformé en modèle en étoile.

Tables générées :
- `dim_geographie`
- `dim_election`
- `dim_candidat_liste`
- `fact_participation`
- `fact_resultats_liste`

Grain des facts :
- `fact_participation` : 1 ligne = 1 commune pour 1 tour et 1 annee
- `fact_resultats_liste` : 1 ligne = 1 candidat/liste dans 1 commune, pour 1 tour et 1 annee

### Export CSV des tables du modele en etoile
Nécessite de run le pipeline de preprocessing pour générer `processed_data/elections_flat.csv` avant.
```powershell
python -m src.starschema.build_star_schema --input processed_data/elections_flat.csv --output-dir processed_data/star_schema --export csv
```

### Usage en DataFrames pandas (insertion BDD directe)
```python
import pandas as pd

from src.starschema.star_schema import build_star_schema, export_tables_dataframes

flat = pd.read_csv("processed_data/elections_flat.csv", sep=";", encoding="latin-1", dtype="string")
tables = build_star_schema(flat)
tables_df = export_tables_dataframes(tables)
```

## Pipeline INSEE
Nécessite de run le pipeline schéma étoile pour générer `processed_data/star_schema/dim_geographie.csv` avant.
```powershell
python -m src.insee_processing.run_flatten_dossier_complet
```

Le script filtre `CODGEO` a partir de `processed_data/star_schema/dim_geographie.csv` et genere un CSV par `target_table`.

### Export CSV minimal (INSEE)
```powershell
python -m src.insee_processing.run_flatten_dossier_complet \
  --raw data/dossier_complet_2025/dossier_complet_2025.csv \
  --mapping src/insee_processing/mapping_dossier_complet.csv \
  --meta data/dossier_complet_2025/meta_dossier_complet.csv \
  --dim-geo processed_data/star_schema/dim_geographie.csv \
  --output-dir processed_data/insee/dossier_complet_2025_flattened
```

### Export DataFrame dict minimal (INSEE)
```python
from pathlib import Path

from src.insee_processing import flatten_dossier_complet_tables

tables = flatten_dossier_complet_tables(
    raw_path=Path("data/dossier_complet_2025/dossier_complet_2025.csv"),
    mapping_path=Path("src/insee_processing/mapping_dossier_complet.csv"),
    meta_path=Path("data/dossier_complet_2025/meta_dossier_complet.csv"),
    dim_geo_path=Path("processed_data/star_schema/dim_geographie.csv"),
)
```
