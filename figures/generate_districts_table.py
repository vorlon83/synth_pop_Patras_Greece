"""
Regenerate Synthetic_Population_manuscript/districts.csv and districts_table.tex
from the current canonical data/gis_district_statistics.csv.

The old districts.csv (committed under Synthetic_Population_manuscript/) was
generated from a stale/superseded pipeline run and its numeric columns no
longer agree with data/gis_district_statistics.csv. This script:

  1. Reads the CURRENT canonical data/gis_district_statistics.csv (Greek NAME,
     numeric columns — source of truth).
  2. Reads the OLD Synthetic_Population_manuscript/districts.csv ONLY to
     recover the DISTRICT_ID -> English NAME mapping (its numeric columns are
     stale and are discarded).
  3. Joins current numeric data to the English names by DISTRICT_ID.
  4. Sorts by total_people descending.
  5. Writes a new districts.csv (same column layout as the old file) and a
     districts_table.tex longtable (same boilerplate/structure as the current
     file at that path), both fully consistent with the canonical CSV.

Run from the repository root:
    python figures/generate_districts_table.py
"""
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANONICAL_CSV = os.path.join(ROOT, "data", "gis_district_statistics.csv")
OLD_DISTRICTS_CSV = os.path.join(ROOT, "Synthetic_Population_manuscript", "districts.csv")
OUT_CSV = os.path.join(ROOT, "Synthetic_Population_manuscript", "districts.csv")
OUT_TEX = os.path.join(ROOT, "Synthetic_Population_manuscript", "districts_table.tex")

COLUMNS = [
    "DISTRICT_ID", "NAME", "pop2021", "total_people", "pop_accuracy",
    "total_households", "num_buildings", "buil_with_households", "fill_rate",
]

# ── 1+2. Load current canonical numeric data and old ID->English-name map ──
with open(CANONICAL_CSV, newline="", encoding="utf-8") as f:
    canonical_rows = list(csv.DictReader(f))

id_to_english_name = {}
with open(OLD_DISTRICTS_CSV, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        id_to_english_name[int(row["DISTRICT_ID"])] = row["NAME"].strip()

missing = [row["DISTRICT_ID"] for row in canonical_rows
           if int(row["DISTRICT_ID"]) not in id_to_english_name]
if missing:
    raise SystemExit(f"DISTRICT_IDs missing from old English-name mapping: {missing}")


def title_case_name(name):
    """Title-case an English district name. The old districts.csv stores names
    in ALL CAPS (with one stray lowercase, 'notia'); Python's str.title()
    correctly reproduces the display style used in the old districts_table.tex
    (e.g. 'ZAROUCHLEIKA' -> 'Zarouchleika', 'AG. SOFIA' -> 'Ag. Sofia',
    'AGYIA (notia)' -> 'Agyia (Notia)')."""
    return name.title()


# ── 3. Join current numeric data to English names ──────────────────────────
merged = []
for row in canonical_rows:
    did = int(row["DISTRICT_ID"])
    merged.append({
        "DISTRICT_ID": did,
        "NAME": title_case_name(id_to_english_name[did]),
        "pop2021": int(row["pop2021"]),
        "total_people": int(row["total_people"]),
        "pop_accuracy": round(float(row["pop_accuracy"]), 1),
        "total_households": int(row["total_households"]),
        "num_buildings": int(row["num_buildings"]),
        "buil_with_households": int(row["buil_with_households"]),
        "fill_rate": round(float(row["fill_rate"]), 1),
    })

# ── 4. Sort by total_people descending ──────────────────────────────────────
merged.sort(key=lambda r: r["total_people"], reverse=True)

# ── verify sums against canonical values ────────────────────────────────────
sum_people = sum(r["total_people"] for r in merged)
sum_hh = sum(r["total_households"] for r in merged)
sum_bld = sum(r["num_buildings"] for r in merged)
sum_buil = sum(r["buil_with_households"] for r in merged)
assert sum_people == 182179, f"total_people sum mismatch: {sum_people}"
assert sum_hh == 71132, f"total_households sum mismatch: {sum_hh}"
assert sum_bld == 32734, f"num_buildings sum mismatch: {sum_bld}"
assert sum_buil == 32734, f"buil_with_households sum mismatch: {sum_buil}"
assert all(r["fill_rate"] == 100.0 for r in merged), "not all fill_rate == 100.0"
assert len(merged) == 55, f"expected 55 districts, got {len(merged)}"
print(f"Verified: N={len(merged)}, sum total_people={sum_people:,}, "
      f"sum total_households={sum_hh:,}, sum num_buildings={sum_bld:,}, "
      f"sum buil_with_households={sum_buil:,}, all fill_rate==100.0")

# ── 5. Write districts.csv ──────────────────────────────────────────────────
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=COLUMNS)
    writer.writeheader()
    for r in merged:
        writer.writerow({
            "DISTRICT_ID": r["DISTRICT_ID"],
            "NAME": r["NAME"],
            "pop2021": r["pop2021"],
            "total_people": r["total_people"],
            "pop_accuracy": f'{r["pop_accuracy"]:.1f}',
            "total_households": r["total_households"],
            "num_buildings": r["num_buildings"],
            "buil_with_households": r["buil_with_households"],
            "fill_rate": f'{r["fill_rate"]:.1f}',
        })
print(f"Wrote {OUT_CSV}")

# ── 6. Write districts_table.tex (same boilerplate as the current file) ────
PREAMBLE = r"""\begin{footnotesize}
\setlength\tabcolsep{4pt}
\begin{longtable}{rp{3.2cm}rrrrrrr}
\caption{District-level spatial assignment results (all 55 districts, sorted by assigned population).}\label{tab:results}\\
\toprule
\textbf{ID} & \textbf{Name} & \textbf{pop2021} & \textbf{total\_people} & \textbf{pop\_acc.\,\%} & \textbf{total\_HH} & \textbf{buildings} & \textbf{with\_HH} & \textbf{fill\,\%} \\
\midrule
\endfirsthead
\multicolumn{9}{l}{\footnotesize\textit{(continued from previous page)}}\\
\toprule
\textbf{ID} & \textbf{Name} & \textbf{pop2021} & \textbf{total\_people} & \textbf{pop\_acc.\,\%} & \textbf{total\_HH} & \textbf{buildings} & \textbf{with\_HH} & \textbf{fill\,\%} \\
\midrule
\endhead
\midrule
\multicolumn{9}{r}{\footnotesize\textit{(continued on next page)}}\\
\endfoot
\bottomrule
\endlastfoot
"""

FOOTER = r"""\end{longtable}
\end{footnotesize}
"""

lines = [PREAMBLE]
for r in merged:
    lines.append(
        f'{r["DISTRICT_ID"]} & {r["NAME"]} & {r["pop2021"]} & {r["total_people"]} & '
        f'{r["pop_accuracy"]:.1f} & {r["total_households"]} & {r["num_buildings"]} & '
        f'{r["buil_with_households"]} & {r["fill_rate"]:.1f} \\\\\n'
    )
lines.append(FOOTER)

with open(OUT_TEX, "w", encoding="utf-8") as f:
    f.write("".join(lines))
print(f"Wrote {OUT_TEX}")
