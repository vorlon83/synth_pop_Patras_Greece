# Data Setup

`data/` and `docs/` are not yet in this folder. Everything below is sourced from the old working
copy at `..\GIS-paper-main\` (sibling folder). Copy only what's listed — the old folder also
contains backups, logs, and a 1.6 GB third-party shapefile that should **not** be copied in.

Total to copy: **~400 MB** (well under GitHub's limits). The one thing NOT copied
(`greece-260611-free.shp/`, ~1.6 GB) is downloaded separately in step 5.

---

## 1. `data/synthpop/` — canonical population files only

Copy these three files, nothing else from that folder (the rest are superseded backups):

| File | Size | Notes |
|---|---|---|
| `households.json` | 57 MB | full Achaia synthesis, 119,070 HH / 306,021 individuals |
| `patras_households.json` | 22 MB | canonical Patras population, 82,507 HH / 215,927 individuals. SHA-256 `48e4053c0ecd6daf5908c0e2eb5a764402d4b247c034e0157e54491551ded9ab` |
| `patras_households_s3.json` | 25 MB | S3 (WG-reweighted) variant, 92,261 HH / 215,920 individuals — used only for the S3-vs-shuffle robustness check |

**Do not copy:** `households_pre_band14fix.json`, `patras_households_new.json`,
`patras_households_pre_edu_reweight.json`, `patras_households_repaired.json`,
`patras_households_edu_reweighted.json` (duplicate of the canonical file), `repair_manifest.json`.

```powershell
$src = "..\GIS-paper-main\data\synthpop"
$dst = "data\synthpop"
New-Item -ItemType Directory -Force $dst | Out-Null
Copy-Item "$src\households.json" $dst
Copy-Item "$src\patras_households.json" $dst
Copy-Item "$src\patras_households_s3.json" $dst
```

---

## 2. `data/PATRAS_GIS_DATA/`, `data/SCHOOLS/`, `data/elstat_2021/`, `data/abm_results/` — copy whole folders

```powershell
$src = "..\GIS-paper-main\data"
Copy-Item "$src\PATRAS_GIS_DATA" "data\PATRAS_GIS_DATA" -Recurse
Copy-Item "$src\SCHOOLS" "data\SCHOOLS" -Recurse
Copy-Item "$src\elstat_2021" "data\elstat_2021" -Recurse
Copy-Item "$src\abm_results" "data\abm_results" -Recurse
Copy-Item "$src\gis_district_statistics.csv" "data\"
Copy-Item "$src\initial_state.geojson" "data\"
Copy-Item "$src\schools.geojson" "data\"
```

**Known issue in this source data:** `PATRAS_GIS_DATA\GEITONIES_PATRAS\EGLYKADA.dbf` and
`geitonies_08.dbf` (and the district name in `gis_district_statistics.csv`) still carry an old
typo, **ΕΓΚΛΥΚΑΔΑ** instead of the correct **ΕΓΛΥΚΑΔΑ**. This was fixed once already but the fix
never made it back into this local folder — it only exists in a leftover clone at
`C:\tmp_ghcheck2` on this machine (from the deleted GitHub repo). If you want the corrected
files, copy from there instead:

```powershell
Copy-Item "C:\tmp_ghcheck2\data\PATRAS_GIS_DATA\GEITONIES_PATRAS\EGLYKADA.dbf" "data\PATRAS_GIS_DATA\GEITONIES_PATRAS\" -Force
Copy-Item "C:\tmp_ghcheck2\data\PATRAS_GIS_DATA\GEITONIES_PATRAS\geitonies_08.dbf" "data\PATRAS_GIS_DATA\GEITONIES_PATRAS\" -Force
Copy-Item "C:\tmp_ghcheck2\data\gis_district_statistics.csv" "data\" -Force
```

Not critical (cosmetic, one district's name in one CSV column) — skip if you'd rather not depend
on that leftover folder.

---

## 3. `data/eurostat/` — validation reference tables

These currently sit under `validation\` in the old folder (already copied into this repo) — the
same files, just also expected at `data/eurostat/` per this repo's own docs. Either move them or
duplicate them; they're small (~1.6 MB total):

```powershell
New-Item -ItemType Directory -Force "data\eurostat" | Out-Null
Copy-Item "validation\A0802_SFA10_MT_AN_00_2024_00_2024_02_F_EN.pdf" "data\eurostat\"
Copy-Item "validation\ESTAT_ILC_LVPS30_1.0.xml.gz" "data\eurostat\"
Copy-Item "validation\[ilc_lvps08] Persons living with their parents.pdf" "data\eurostat\"
Copy-Item "validation\ilc_lvps08`$defaultview_spreadsheet.xlsx" "data\eurostat\"
Copy-Item "validation\ilc_lvps08__custom_21828227_spreadsheet.xlsx" "data\eurostat\"
Copy-Item "validation\ilc_lvps30`$defaultview_HORIZONTAL_BAR_2026-06-14_19_17_15.pdf" "data\eurostat\"
```

---

## 4. `docs/` — methodology & reference docs

```powershell
Copy-Item "..\GIS-paper-main\docs" "docs" -Recurse
```

Contents: `ASSUMPTIONS_AND_DECISIONS.md`, `GLOSSARY.md`, `REVIEWER_NOTES.md`, `codebook.md`,
`population_canonical.md` (each with a `.pdf` export).

**Bonus, not in the local folder at all:** `docs/story.md` — a well-written narrative walkthrough
of the whole pipeline ("The Life of a Synthetic Household…") that was written directly for the
GitHub release and never saved locally. Only remaining copy is in the leftover clone:

```powershell
Copy-Item "C:\tmp_ghcheck2\docs\story.md" "docs\"
```

Worth grabbing — it's good documentation and otherwise gone for good once that temp folder is
cleaned up.

---

## 5. Third-party OSM data (do NOT copy — download fresh)

`data/greece-260611-free.shp/` (~1.6 GB) is a Geofabrik OSM extract, already in `.gitignore`.
Download separately:

1. Get the Greece shapefile extract from Geofabrik, date code `260611` (2026-06-11).
2. Unpack to `data/greece-260611-free.shp/`.
3. The pipeline only needs two files from inside it: `gis_osm_landuse_a_free_1.shp` and
   `gis_osm_buildings_a_free_1.shp`.

Stages 1–3 and the validation cells (Stage 9 of `pipeline.ipynb`) run fine without this.

---

## 6. Licensed source microdata (do NOT commit)

`Thesis_Synthpop-main/it_microdata_preprocess/SOG_Microdati_2016.txt` (3.6 MB, already present
in this folder) is the raw ISTAT 2016 microcensus file — licensed, not redistributable. It's
already in `.gitignore` so a plain `git add` won't pick it up, but double check before pushing
(`git status` should not show it). The **derived** aggregate templates
(`household_compositions.json`, `household_compositions_s3.json`, already in this folder) are
what the pipeline actually consumes and are fine to publish.

---

## Canonical checksums

| File | HH | Individuals |
|---|---|---|
| `data/synthpop/households.json` | 119,070 | 306,021 |
| `data/synthpop/patras_households.json` | 82,507 | 215,927 |
| `data/synthpop/patras_households_s3.json` | 92,261 | 215,920 |

SHA-256 for `patras_households.json`: `48e4053c0ecd6daf5908c0e2eb5a764402d4b247c034e0157e54491551ded9ab`
(full record in `docs/population_canonical.md` once copied per step 4).

> These counts and the SHA-256 describe the **canonical files shipped with the release**, and the checksum is for verifying an intact download. A fresh run of the synthesis pipeline (`HOWTO_REPRODUCE.md`, Steps 1–3) is seeded (`seed=42`) but **not bit-identical across Python/NumPy versions**: it reproduces a demographically equivalent population to within ~0.02% of these counts (all `verify_population.py` structural gates pass), not a byte-identical copy. Use the shipped canonical files for exact downstream (GIS/ABM) reproduction.
