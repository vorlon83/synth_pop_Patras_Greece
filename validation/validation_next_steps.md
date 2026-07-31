# Validation Next Steps: Instructions for Claude Code

## Governing principle (read first)

The synthesis produces co-residence by gender and age only, with no relationships. Therefore the only quantities that can be compared to external data without a category mismatch are relationship-free: household size (already done, JSD = 0.009 bits) and living-alone rate by age. Every relationship-based benchmark (living with parents, couple type, lone parent) describes something the method does not model and must not be presented as a direct validator. Build the resubmission validation on the relationship-free metrics. The temptation to use the richer relationship-based tables is the main way this section goes wrong.

Tags: [VASILIS] = data access or download (Claude Code's sandbox cannot reach the Eurostat or ELSTAT servers); [CODE] = computation Claude Code does on the canonical population.

---

## Tier 1: immediate, for this resubmission (no data application needed)

### 1.1 Elderly living alone — the primary new external check ✅ COMPLETE

**Status: inserted into main.tex (2026-06-21)**

Greek reference (ilc_lvps30, A1_GE65, Greece 2025, total sex): **35.0%**
Source: Eurostat bar chart PDF in `validation/ilc_lvps30$defaultview_HORIZONTAL_BAR_2026-06-14_19_17_15.pdf`

Synthetic results (canonical population, seed 42):
- 65+ overall: 19.1% (males 7.8%, females 28.2%)
- 75+ overall: 25.9% (males 10.7%, females 37.0%)
- Gap: **−15.9 pp** (synthetic under-produces, consistent with matcher residual)

Written into main.tex Section "Elderly living alone" and validation summary table.
Per-sex Greek reference (A1_GE65, males/females separately) not yet extracted — bar chart shows only total. If needed for revision, download the data table from Eurostat.

### 1.2 One-person households by age — census-based regional check
Source: ELSTAT Table A07, "one-person households by age group, sex, region," Western Greece. Census-based, regional, relationship-free, and not used as an IPF constraint.

**2026-06-22 — CLOSED.** ELSTAT does not publish a household-level table (one-person households by age group) in its public release. Communication with ELSTAT confirmed this is not available. All publicly available ELSTAT 2021 tables are individual-level population counts (A01–C06 series). The validation rests on the available external checks: ilc_lvps30 (Eurostat, Section 1.1), household size JSD (Section 1.3), and Patras-level education distribution (Section 1.6). No further action possible.

### 1.6 New: ELSTAT 2021 Patras population tables — analysis complete ✅

**Source files:** `data/elstat_2021/` — 24 xlsx tables, ELSTAT 2021 Census. All use the Cell Key Method (CKM) for confidentiality: < 20% of cells are lightly perturbed; zero values remain zero; row/column sums may not add exactly. See `data/elstat_2021/A1602_SAM03_MT_DC_00_2021_00_2099_01_F_GR.pdf`.

**Table inventory:**
- A01–A12: Regional Unit (Περιφερειακή Ενότητα) level — age/sex, marital status, education, nationality, women/children
- B01–B05: Municipality (Δήμος) level — age/sex, age/education, nationality
- C01–C06: Settlement or Municipal Community level — age/sex, marital status, education

**Patras-level findings (Δήμος Πατρέων, code 2423701):**

*Sex and age — perfect match (both dimensions re-fitted at Patras level by IPF sub-run):*
- Male: synthetic 48.4% vs ELSTAT B01 48.4% — gap ~0 pp ✅
- Female: synthetic 51.6% vs ELSTAT B01 51.6% — gap ~0 pp ✅
- All 6 age bands (0-14 through 75+): gap ≤ 0.0 pp ✅

*Education — Patras-level deviations (B02, approximate mapping ISTAT→ELSTAT categories):*
| Category | Synthetic | ELSTAT B02 | Gap |
|---|---|---|---|
| University+ (Doctoral/Masters/University/TEI) | 19.6% | 22.9% | −3.3 pp |
| Post-secondary (IEK/Colleges) | 4.0% | 4.1% | −0.1 pp ✅ |
| High school diploma | 26.4% | 32.9% | −6.6 pp |
| Vocational / Junior high | 16.9% | 11.1% | +5.8 pp |
| Elementary | 18.7% | 15.6% | +3.1 pp |
| No/incomplete schooling | 9.5% | 8.4% | +1.1 pp |
| Born post-2016 (unclassified) | 5.0% | 4.9% | ~0 pp ✅ |

Education gaps (up to −6.6 pp high school, +5.8 pp vocational) are consistent with: (a) the Achaia-level IPF residual carrying through to Patras, (b) imperfect ISTAT→ELSTAT education category mapping, and (c) cross-national differences in the education distribution structure. The mapping is approximate — Italian education categories do not align perfectly with Greek ones.

*Marital status (C03, Patras 2021) — contextual only, not a direct household validator:*
- 75+: widowed = 7,970/18,943 = **42.1%**; non-married total = 50.5%
- 60-74: widowed = 4,801/35,739 = 13.4%
- Context for ilc_lvps30: synthetic 75+ living-alone rate = 25.9%; synthetic 65+ = 19.1%; Eurostat ilc_lvps30 Greek reference = 35.0% (65+). The 42.1% widowhood rate for 75+ confirms there is structural pressure toward elderly singletons in Patras that the Italian template prior under-produces.

**Manuscript implication:** Education deviations can now be quantified at the Patras level (not just the Achaia IPF residual). Could add a brief note: "Education marginals at the Patras municipality level show deviations of up to 6.6 pp (high school category), consistent with the Achaia-level IPF residual and cross-national education-category mapping uncertainty." This directly addresses any reviewer concern about Patras-specific education fit.

### 1.3 Household size — already done, keep as the anchor
JSD = 0.009 bits vs Western Greece (χ² = 3857.1, df=4, confirmed on canonical 82,507-HH population). State it once as the relationship-free anchor; do not re-litigate the chi-square.

### 1.4 Young adults — context only, with an explicit caveat (do not over-claim)
Source: Eurostat `ilc_lvps08` (not lvps09), "young adults 18-34 living with their parents," Greece.
- This is NOT a direct validator. EU-SILC's definition counts financially dependent students who have physically moved out, so it overstates physical co-residence, and your synthesis cannot identify "parents" at all. The comparable synthetic quantity ("18-34 not in a one-person household") is broader and different.
- [CODE] If included at all, compute the synthetic age-proxy ("18-29 co-resident with at least one adult 16+ years older") and report it beside the ilc_lvps08 figure only with a sentence stating the two measure different constructs. Otherwise omit. Do not write a sentence implying the synthetic young-adult co-residence matches the Eurostat "with parents" figure.

### 1.5 [CODE] Write the Tier-1 validation subsection
Add the elderly-living-alone comparison (1.1) and, when available, the one-person-by-age comparison (1.2) to the Age-Based Co-Residence subsection. Frame as: relationship-free structural dimensions validated against independent Greek survey and census data; deviations reported with the matcher-residual mechanism. This directly answers both reviewers' "validation is circular / size is not structure" criticism with external, non-fitted, structure-relevant data.

---

## Tier 2: short-term, initiate now, upgrade if data arrives before the defense

### 2.1 SHARE — elderly co-residence gold standard
- [VASILIS] Register now: read the Conditions of Use, sign the SHARE User Statement, email share-rdc@centerdata.nl. Standard access, no proposal, typically granted within days to a few weeks. Target SHARE release 9-0-0, Greece wave 8.
- [CODE] Stage the comparison script now, before data arrives, against the documented variables (household id, age, partner-in-household, child-in-household), so it computes the 65+ living-arrangement breakdown the moment the data lands. SHARE is the strongest available benchmark for the exact subpopulation the matcher gets wrong, so if it arrives in time it upgrades Tier 1.1 from a single aggregate to a full distribution.

---

## Tier 3: defer to future work, state in the paper

### 3.1 EU-SILC Greece cross-sectional UDB
Entity recognition (~4 weeks) plus proposal approval (~8 weeks), so roughly three months, beyond the resubmission window. It would give full age-based structure (multigenerational shares, within-household age spans) against independent Greek rosters. [VASILIS] start the entity-recognition step now if you intend the follow-up paper; mention as in-progress in Future Work.

### 3.2 ELSTAT Scientific Use Files (LFS, HBS)
2-4 months via the CIMES portal; the full structural gold standard, for a future paper. Mention in Future Work so the reviewers see you understand the gold-standard path and are not claiming current validation is final.

---

## The honest sentence for the paper

External validation of household structure is feasible on the relationship-free dimensions the method produces (household size and living-alone rate by age), against which the population is validated here using independent Eurostat and ELSTAT data not used as synthesis constraints. Relationship-based structure and the full cross-national joint-dependency remain validatable only through survey microdata (SHARE, EU-SILC) whose access is in progress, and are deferred to future work. This replaces "validation cannot escape the construction constraints" with a bounded, true claim.

---

## Cautions (each one is a way this section fails review)

- Never compare a relationship-free synthetic metric to a relationship-based benchmark. The ilc_lvps08/09 "living with parents" figure is the specific trap: it is relationship-defined and SILC-inflated, and your synthesis is neither.
- Report the elderly-living-alone comparison as found. Under- or over-production vs Greece is a result with a known mechanism, not something to tune.
- No benchmark enters the paper unverified. Confirm each downloaded figure is the Greece value, the correct year, and the matching age bands and sex breakdown before it is cited. A misidentified benchmark is as damaging as a fabricated number.
- Match age bands before comparing: ilc_lvps30 uses 65+; ELSTAT A07 and your synthesis use 5-year bands. Aggregate the synthetic side to the benchmark's bands, do not split the benchmark.
- Claude Code cannot reach the Eurostat or ELSTAT servers; all downloads are [VASILIS], and Claude Code computes the synthetic side and the comparison from the uploaded values.

---

## Sequencing

1. [VASILIS] Download `ilc_lvps30` (Greece, A1_GE65, by sex) today; it needs no registration.
2. [CODE] Compute the synthetic 65+ and 75+ living-alone rates by sex and build the comparison; draft the subsection (1.1, 1.5).
3. [VASILIS] Request ELSTAT A07 and register for SHARE in parallel.
4. [CODE] Stage the SHARE comparison script (2.1) so it runs on arrival.
5. Fold A07 and SHARE in if they arrive before resubmission; otherwise cite them as in-progress and rest the resubmission on 1.1 and 1.3.
