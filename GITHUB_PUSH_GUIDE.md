# Guide: Pushing this repo to GitHub

Current state: not yet a git repository (`git status` fails with "not a git repository").
`.gitignore` already exists at the repo root and is correct. `CuwTPNMB/` (a 2GB undocumented
duplicate of `data/`) has been deleted. The GitHub repo itself has already been created — this
guide only covers connecting this local folder to it and pushing.

---

## What can't be uploaded, and where to get it back

Three things are excluded by `.gitignore` and will **not** be on GitHub. Anyone (including future
you) who clones the repo needs to reconstruct them separately to run the full pipeline end to end.

### 1. Geofabrik OSM extract for Greece — download it fresh

```
data/greece-260611-free.shp/
```

~1.6GB, and individually contains five files over GitHub's 100MB hard per-file limit (up to
451MB) — this would make `git push` fail outright if it were ever staged, not just bloat the repo.

**To get it back:**
1. Download the Greece shapefile extract from **Geofabrik**, date code `260611` (2026-06-11):
   `https://download.geofabrik.de/europe/greece.html` (or the dated archive if that exact snapshot
   is no longer the "latest" — Geofabrik keeps dated historical extracts).
2. Unpack to `data/greece-260611-free.shp/`.
3. The pipeline only actually reads two files from inside it: `gis_osm_landuse_a_free_1.shp` and
   `gis_osm_buildings_a_free_1.shp`. The rest of the extract can be discarded if disk space matters.

Pipeline stages 1–3 and the validation cells (Stage 9 of `pipeline.ipynb`) run fine without this
file — only the GIS spatial-assignment stage (Stages 4–8) needs it.

### 2. ISTAT 2016 microcensus microdata — licensed, not publicly redistributable

```
Thesis_Synthpop-main/it_microdata_preprocess/SOG_Microdati_2016.txt
```

3.6MB. This is licensed source microdata from Istat (the Italian national statistics institute) —
not something that can simply be re-downloaded from a public URL; access requires a research
data request through Istat's own microdata access process
(`https://www.istat.it/en/analysis-and-products/microdata` — the "Sample survey on households"
microdata line is the relevant one for the 2016 household composition census this pipeline uses).
**Whoever needs to fully reproduce the IPF/household-synthesis stage from raw microdata has to
request this file from Istat directly under their license terms.**

The pipeline itself does not need the raw file to run, though — it consumes the **derived**
aggregate templates, which are small, non-restricted, and already committed:
```
Thesis_Synthpop-main/it_microdata_preprocess/household_compositions.json
Thesis_Synthpop-main/it_microdata_preprocess/household_compositions_s3.json
```
These are what `main_ipf_pipeline.py` actually reads. The raw microdata file is only needed if
someone wants to regenerate the templates themselves from scratch rather than trust the shipped
derived files.

### 3. Superseded population-file variants — not needed, not a download

```
data/synthpop/households_pre_band14fix.json
data/synthpop/patras_households_new.json
data/synthpop/patras_households_pre_edu_reweight.json
data/synthpop/patras_households_repaired.json
data/synthpop/patras_households_edu_reweighted.json
data/synthpop/repair_manifest.json
```

These are pre-bugfix backups kept locally for reference, not inputs anything downstream reads.
Excluded to save space; there's nothing to download because the canonical replacements
(`households.json`, `patras_households.json`, `patras_households_s3.json`) are what actually ship
in the repo.

---

## What IS included (~270MB total)

Everything else: the canonical population files (`data/synthpop/households.json`,
`patras_households.json`, `patras_households_s3.json` — 56/22/25MB), `data/PATRAS_GIS_DATA/`,
`data/SCHOOLS/`, `data/elstat_2021/`, `data/abm_results/`, `data/gis_district_statistics.csv`, all
source code, `figures/`, the manuscript folder, and `main.pdf`. No single file in this set exceeds
GitHub's 100MB limit, and total repo size lands around ~270MB — comfortably under GitHub's ~1GB
soft-recommendation.

---

## The remote already exists and is not empty

`https://github.com/vorlon83/synth_pop_Patras_Greece` already has **2 commits** and root-level
content (`Thesis_Synthpop-main/`, `abm-patras-greece-main/`, `figures/`, `gis/`, `validation/`,
`README.md`, `main.pdf`, `pipeline.ipynb`, etc.) — but **no `data/` folder at all**, confirming the
gap this whole guide exists to close. This local folder has no `.git` yet, so this is not a fresh
push — it's reconciling a local folder against a remote that already has related-but-incomplete
history. Do not `git init` + force-push; that would blow away the existing 2 commits.

```bash
cd "path/to/synth_pop_Patras_Greece"

# 1. Init, connect the remote, capture everything local as its own commit first
git init -b main
git remote add origin https://github.com/vorlon83/synth_pop_Patras_Greece.git
git add .

git status
# Confirm you do NOT see data/greece-260611-free.shp/, SOG_Microdati_2016.txt, or any of the
# superseded data/synthpop/*.json variants staged. If any show up, fix .gitignore before committing.

git commit -m "Add full data payload, .gitignore, and cleanup"

# 2. Pull in the existing remote history and merge
git fetch origin
git merge origin/main --allow-unrelated-histories -m "Merge existing remote history"
```

**Expect merge conflicts** on any file that exists in both places with different content —
`README.md`, `main.pdf`, and `HOWTO_REPRODUCE.md` are the likely candidates, since all three exist
on the remote already and may have since diverged locally. Git will list conflicted files and stop;
resolve each by hand (`git status` shows them, edit to keep whichever version — or a merge of
both — then `git add <file>`), then:

```bash
git commit          # completes the merge once conflicts are resolved
git push -u origin main
```

If you'd rather not deal with merge conflicts and are confident the local copy should simply
**replace** whatever's on the remote (i.e. the remote's 2 commits have nothing worth keeping),
the alternative is a history-discarding force push instead of the merge above:
```bash
git push -u origin main --force
```
This permanently overwrites the remote's existing 2 commits — only do this if you're sure nothing
in that old history is needed, since it can't be undone from your side once pushed.

**Authentication:** if this is the first push from this machine, GitHub will reject a plain
password over HTTPS (retired) — use a Personal Access Token when prompted, or switch to SSH first
if you already have a key registered with GitHub:
```bash
git remote set-url origin git@github.com:vorlon83/synth_pop_Patras_Greece.git
```

## Verify after pushing

- Open the repo on github.com and confirm `data/` now appears with `PATRAS_GIS_DATA/`, `SCHOOLS/`,
  `synthpop/`, `elstat_2021/`, `abm_results/` — but not `greece-260611-free.shp/`.
- Confirm `SOG_Microdati_2016.txt` is **not** present anywhere.
- Check Settings → General for the reported repo size — expect roughly ~270MB, not multiple GB.
- If you merged (not force-pushed), spot-check that the merge conflict resolutions on
  `README.md`/`main.pdf`/`HOWTO_REPRODUCE.md` kept the version you actually intended.
- Consider adding the two download-source notes above (Geofabrik + Istat) to `DATA_SETUP.md` or
  `README.md` directly, so a future cloner doesn't have to find this guide to know where the
  missing pieces come from.
