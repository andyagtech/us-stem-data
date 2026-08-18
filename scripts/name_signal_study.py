#!/usr/bin/env python3
"""
Measurement study: does the name composition of a graduating cohort carry
usable signal about that cohort's reported non-resident-alien (NRA) share?

THIS IS A CALIBRATION STUDY, NOT A CLASSIFIER.
A name indicates likely origin, not immigration status. Per-person inference
from name to visa status is invalid. The only question tested here is whether
the *distribution* of name features across a cohort predicts the cohort's
*reported* NRA share as filed by the institution to IPEDS.

Stages (run with --stage or --all):
  ipeds     extract IPEDS Completions doctorate cells (AWLEVEL=17) for our
            universities into a compact cache
  cohorts   aggregate our dissertation records into (unitid, cip2, year) cells
            with name-derived aggregate features
  join      join the two, report attrition
  model     correlation + held-out-by-university regression vs. baseline
  probe     failure analysis: by university, by field, by cohort size, by feature

Outputs land in the scratchpad dir (--out), not in the repo.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import random
import re
import sys
import zipfile
from collections import Counter, defaultdict

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
IPEDS_DIR = os.path.join(PROJECT_ROOT, "data", "ipeds")
PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
UNIVERSITIES_JSON = os.path.join(PROJECT_ROOT, "pipeline", "universities.json")

DEFAULT_OUT = os.environ.get(
    "NAME_SIGNAL_OUT",
    "/private/tmp/claude-501/-Users-andy-usds-china/"
    "5f48248f-d0fc-4a8c-9b94-e31e685a7ff6/scratchpad",
)

# IPEDS years where CIPCODE/AWLEVEL/MAJORNUM/CTOTALT/CNRALT all exist AND the
# local copy covers every institution (the 2008/2009 files on disk are partial:
# 20 and 36 of our 100 institutions, vs 100 from 2010 on).
YEARS = list(range(2010, 2026))

# AWLEVEL 17: research/scholarship doctorate.
AWLEVEL_DOCTORATE = "17"

# Name categories emitted by scripts/name_classifier.py and stored in
# data/processed/*/{key}.json record[3].
CATEGORIES = [
    "chinese", "indian", "korean", "arabic", "vietnamese",
    "iranian", "turkish", "excluded_ambiguous", "other",
]
# Categories that are plausibly correlated with international student flows.
FOREIGN_CATS = ["chinese", "indian", "korean", "arabic", "vietnamese",
                "iranian", "turkish"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def read_csv_bom(path_or_fh):
    """IPEDS CSVs carry a UTF-8 BOM on the first column name, so
    row.get('UNITID') returns None. Return (reader, first_fieldname)."""
    r = csv.DictReader(path_or_fh)
    first = r.fieldnames[0]
    return r, first


def to_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def load_universities():
    with open(UNIVERSITIES_JSON) as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# stage: ipeds
# ---------------------------------------------------------------------------

def stage_ipeds(out_dir):
    univ = load_universities()
    unitids = {}
    for key, v in univ.items():
        uid = v.get("unitid")
        if uid:
            unitids[str(uid)] = key
    print(f"[ipeds] {len(unitids)} universities with a UNITID", file=sys.stderr)

    rows = []
    for year in YEARS:
        cands = [p for p in glob.glob(os.path.join(IPEDS_DIR, f"[Cc]{year}_[aA].csv"))
                 if "_rv" not in os.path.basename(p).lower()]
        fh = None
        zf = None
        if cands:
            fh = open(cands[0], newline="", encoding="utf-8-sig", errors="replace")
        else:
            zpath = os.path.join(IPEDS_DIR, f"C{year}_A.zip")
            if os.path.exists(zpath):
                zf = zipfile.ZipFile(zpath)
                inner = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
                import io
                fh = io.TextIOWrapper(zf.open(inner), encoding="utf-8-sig",
                                      errors="replace", newline="")
        if fh is None:
            print(f"[ipeds] {year}: no file", file=sys.stderr)
            continue

        r, first = read_csv_bom(fh)
        n = 0
        for row in r:
            uid = (row.get(first) or "").strip()
            if uid not in unitids:
                continue
            if (row.get("AWLEVEL") or "").strip() != AWLEVEL_DOCTORATE:
                continue
            if (row.get("MAJORNUM") or "").strip() != "1":
                continue
            tot = to_int(row.get("CTOTALT"))
            nra = to_int(row.get("CNRALT"))
            if tot is None or nra is None:
                continue
            rows.append((year, uid, unitids[uid],
                         (row.get("CIPCODE") or "").strip(), tot, nra))
            n += 1
        fh.close()
        if zf:
            zf.close()
        print(f"[ipeds] {year}: {n} doctorate cells", file=sys.stderr)

    path = os.path.join(out_dir, "ipeds_doctorate_cells.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["year", "unitid", "key", "cipcode", "ctotalt", "cnralt"])
        w.writerows(rows)
    print(f"[ipeds] wrote {len(rows)} rows -> {path}", file=sys.stderr)
    return path


# ---------------------------------------------------------------------------
# department -> CIP 2-digit crosswalk (approximate, keyword-based)
# ---------------------------------------------------------------------------

# Ordered rules: first match wins. Deliberately coarse -- we map to the
# 2-digit CIP family, not to a 6-digit program, because our department strings
# are free text scraped from repository metadata and have no CIP anywhere.
CIP2_RULES = [
    ("11", r"computer sci|computing|informatics|information scien|"
           r"information systems|software engineer|data scien|"
           r"artificial intelligen|human.?computer|cyber"),
    ("14", r"engineer|\beng\b|aeronaut|astronaut|astro\b|mechanic|aerospac|"
           r"civil|electrical|chemical engineer|materials scien|"
           r"biomedical engineer|nuclear|petroleum|industrial engineer|"
           r"systems engineer|environmental engineer|operations research"),
    ("26", r"biolog|biochem|microbiolog|genetic|genomic|neurosci|"
           r"molecular|cell biolog|ecolog|physiolog|immunolog|botany|"
           r"zoolog|entomolog|biophysic|bioinformat|computational biolog|"
           r"plant (patholog|scien|biolog)|marine biolog|toxicolog"),
    ("27", r"mathemat|statistic|applied math|biostatistic"),
    ("40", r"physic|chemistr|astronom|astrophys|geolog|geoscien|"
           r"earth scien|earth (system|& space)|atmospheric|atmos|"
           r"oceanograph|marine scien|planetary|nanoscien|"
           r"materials(?! engineer)|meteorolog"),
    ("42", r"psycholog|cognitive scien|clinical psych"),
    ("51", r"nursing|public health|epidemiolog|pharmac|medicine|medical|"
           r"kinesiolog|speech.?language|audiolog|dental|"
           r"health scien|occupational therap|physical therap|"
           r"veterinar|nutrition"),
    ("52", r"business|management|marketing|finance|accounting|mba|"
           r"organizational behav|entrepreneur"),
    ("45", r"economic|sociolog|political scien|government|anthropolog|geograph|"
           r"internationa(l)? (relations|affairs)|public polic|"
           r"criminolog|urban plan"),
    ("13", r"education|\beduc\b|curriculum|instruction|teaching|"
           r"educational (leader|psych|admin)|higher educ|counselor educ"),
    ("23", r"english|literature|rhetoric|comparative lit|writing"),
    ("54", r"history|historical"),
    ("38", r"philosoph|religio|theolog|ethic"),
    ("50", r"music|art history|fine art|theat|dance|design(?! engineer)|"
           r"film|visual art|^art$"),
    ("04", r"architect|city & regional plan|landscape architect"),
    ("16", r"linguistic|spanish|french|german|chinese|japanese|"
           r"classics|slavic|east asian|near eastern|romance lang"),
    ("09", r"communicat|journalis|media stud|film stud"),
    ("03", r"forest|natural resource|wildlife|environmental scien|"
           r"fisheries|conservation|soil|water resource"),
    ("01", r"agricultur|animal scien|agronom|horticultur|crop|"
           r"food scien|poultry|dairy"),
    ("44", r"social work|public administration|public affairs"),
    ("22", r"^law$|juridical|legal stud"),
    ("30", r"interdisciplinar|multidisciplinar|neuroscience program"),
]
CIP2_COMPILED = [(c, re.compile(p, re.I)) for c, p in CIP2_RULES]

CIP2_NAMES = {
    "01": "Agriculture", "03": "Natural Resources", "09": "Communication",
    "11": "Computer Science", "13": "Education", "14": "Engineering",
    "16": "Languages", "22": "Law", "23": "English", "26": "Biological Sciences",
    "27": "Math & Statistics", "30": "Interdisciplinary", "38": "Philosophy",
    "40": "Physical Sciences", "42": "Psychology", "44": "Public Admin",
    "45": "Social Sciences", "50": "Visual & Performing Arts",
    "51": "Health Professions", "52": "Business", "54": "History",
}


def dept_to_cip2(dept: str):
    if not dept:
        return None
    for cip, rx in CIP2_COMPILED:
        if rx.search(dept):
            return cip
    return None


# ---------------------------------------------------------------------------
# stage: cohorts
# ---------------------------------------------------------------------------

def iter_records():
    for sub in ("stem", "nonstem"):
        d = os.path.join(PROCESSED_DIR, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(d, fn)) as fh:
                blob = json.load(fh)
            key = blob.get("key") or fn[:-5]
            for rec in blob["records"]:
                yield key, rec


def stage_cohorts(out_dir, phd_only=True):
    univ = load_universities()
    key_to_unitid = {k: str(v["unitid"]) for k, v in univ.items() if v.get("unitid")}

    cells = defaultdict(Counter)   # (key, cip2, year) -> category counts
    attrition = Counter()
    unmapped_depts = Counter()

    for key, rec in iter_records():
        dept, year, name, cat = rec[0], rec[1], rec[2], rec[3]
        degree = rec[7] if len(rec) > 7 else ""
        attrition["records_total"] += 1
        if key not in key_to_unitid:
            attrition["drop_no_unitid"] += 1
            continue
        if phd_only and degree != "phd":
            attrition["drop_not_phd"] += 1
            continue
        y = to_int(year)
        if y is None or y < YEARS[0] or y > YEARS[-1]:
            attrition["drop_year_out_of_window"] += 1
            continue
        cip2 = dept_to_cip2(dept)
        if cip2 is None:
            attrition["drop_dept_unmapped"] += 1
            unmapped_depts[dept] += 1
            continue
        attrition["kept"] += 1
        cells[(key, cip2, y)][cat] += 1

    path = os.path.join(out_dir, "cohort_cells.csv")
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["key", "unitid", "cip2", "year", "n"] + CATEGORIES)
        for (key, cip2, y), c in sorted(cells.items()):
            n = sum(c.values())
            w.writerow([key, key_to_unitid[key], cip2, y, n]
                       + [c.get(cat, 0) for cat in CATEGORIES])
    print(json.dumps(dict(attrition), indent=2), file=sys.stderr)
    print(f"[cohorts] {len(cells)} cells -> {path}", file=sys.stderr)

    with open(os.path.join(out_dir, "unmapped_departments.txt"), "w") as fh:
        for d, n in unmapped_depts.most_common(300):
            fh.write(f"{n}\t{d}\n")
    return path, dict(attrition), unmapped_depts


# ---------------------------------------------------------------------------
# stage: join
# ---------------------------------------------------------------------------

def load_ipeds_cells(out_dir):
    """Return (by_cell, by_inst_year, by_inst) aggregations.
    by_cell:      (unitid, cip2, year) -> (total, nra)
    by_inst_year: (unitid, year) -> (total, nra)     [CIPCODE 99 preferred]
    by_inst:      unitid -> (total, nra)
    """
    path = os.path.join(out_dir, "ipeds_doctorate_cells.csv")
    by_cell = defaultdict(lambda: [0, 0])
    by_inst_year = defaultdict(lambda: [0, 0])
    by_inst = defaultdict(lambda: [0, 0])
    with open(path) as fh:
        for row in csv.DictReader(fh):
            uid, cip, y = row["unitid"], row["cipcode"], int(row["year"])
            tot, nra = int(row["ctotalt"]), int(row["cnralt"])
            if cip.startswith("99"):
                # institution-level aggregate row: use for totals only,
                # never for cell-level (it would double count).
                by_inst_year[(uid, y)][0] += tot
                by_inst_year[(uid, y)][1] += nra
                by_inst[uid][0] += tot
                by_inst[uid][1] += nra
                continue
            cip2 = cip.split(".")[0].zfill(2)
            by_cell[(uid, cip2, y)][0] += tot
            by_cell[(uid, cip2, y)][1] += nra
    return by_cell, by_inst_year, by_inst


def load_cohort_cells(out_dir):
    path = os.path.join(out_dir, "cohort_cells.csv")
    out = []
    with open(path) as fh:
        for row in csv.DictReader(fh):
            out.append(row)
    return out


def features_from_counts(counts, n):
    """Aggregate, cohort-level name features. All are shares of the cohort."""
    f = {}
    for cat in FOREIGN_CATS:
        f["sh_" + cat] = counts.get(cat, 0) / n
    f["sh_foreign_any"] = sum(counts.get(c, 0) for c in FOREIGN_CATS) / n
    f["sh_ambiguous"] = counts.get("excluded_ambiguous", 0) / n
    f["sh_other"] = counts.get("other", 0) / n
    return f


FEATURE_NAMES = (["sh_" + c for c in FOREIGN_CATS]
                 + ["sh_foreign_any", "sh_ambiguous"])


# ---------------------------------------------------------------------------
# date-quality diagnostic
# ---------------------------------------------------------------------------

def date_quality(out_dir, min_years=6):
    """Empirical proxy for whether a university's record years are award years.

    For each university-year we compute coverage = our PhD record count /
    IPEDS research doctorates awarded. If our dates were award dates and
    harvest coverage were stable, coverage would be roughly flat. Deposit or
    accession dates produce spikes (a bulk digitisation year) and impossible
    values (coverage > 1.5 means more dissertations than doctorates awarded).

    Returns key -> dict(cv, frac_impossible, n_years, median_cov).
    """
    _, by_inst_year, _ = load_ipeds_cells(out_dir)
    ours = defaultdict(int)
    univ = load_universities()
    key_to_unitid = {k: str(v["unitid"]) for k, v in univ.items() if v.get("unitid")}
    for key, rec in iter_records():
        if len(rec) > 7 and rec[7] != "phd":
            continue
        y = to_int(rec[1])
        if y is None or y < YEARS[0] or y > YEARS[-1]:
            continue
        if key not in key_to_unitid:
            continue
        ours[(key, y)] += 1

    per_key = defaultdict(list)
    for (key, y), n in ours.items():
        uid = key_to_unitid[key]
        tot = by_inst_year.get((uid, y), [0, 0])[0]
        if tot >= 10:
            per_key[key].append((y, n / tot))

    out = {}
    for key, pairs in per_key.items():
        if len(pairs) < min_years:
            continue
        covs = [c for _, c in pairs]
        mean = sum(covs) / len(covs)
        var = sum((c - mean) ** 2 for c in covs) / len(covs)
        sd = math.sqrt(var)
        covs_sorted = sorted(covs)
        med = covs_sorted[len(covs_sorted) // 2]
        out[key] = {
            "n_years": len(covs),
            "median_cov": round(med, 3),
            "cv": round(sd / mean, 3) if mean else None,
            "frac_impossible": round(
                sum(1 for c in covs if c > 1.5) / len(covs), 3),
        }
    return out


# ---------------------------------------------------------------------------
# stats helpers (no numpy dependency assumed; use it if available)
# ---------------------------------------------------------------------------

def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    return pearson(rank(xs), rank(ys))


def ols(X, y, ridge=1e-6):
    """Solve (X'X + ridge I) b = X'y by Gaussian elimination. X includes
    an intercept column."""
    p = len(X[0])
    XtX = [[0.0] * p for _ in range(p)]
    Xty = [0.0] * p
    for row, t in zip(X, y):
        for i in range(p):
            Xty[i] += row[i] * t
            for j in range(p):
                XtX[i][j] += row[i] * row[j]
    for i in range(p):
        XtX[i][i] += ridge
    # Gaussian elimination with partial pivoting
    A = [XtX[i][:] + [Xty[i]] for i in range(p)]
    for c in range(p):
        piv = max(range(c, p), key=lambda r: abs(A[r][c]))
        if abs(A[piv][c]) < 1e-12:
            continue
        A[c], A[piv] = A[piv], A[c]
        pv = A[c][c]
        for j in range(c, p + 1):
            A[c][j] /= pv
        for r in range(p):
            if r == c:
                continue
            f = A[r][c]
            if f:
                for j in range(c, p + 1):
                    A[r][j] -= f * A[c][j]
    return [A[i][p] for i in range(p)]


def r2(actual, pred):
    n = len(actual)
    mean = sum(actual) / n
    ss_res = sum((a - p) ** 2 for a, p in zip(actual, pred))
    ss_tot = sum((a - mean) ** 2 for a in actual)
    return 1 - ss_res / ss_tot if ss_tot > 0 else None


def rmse(a, p):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, p)) / len(a))


def mae(a, p):
    return sum(abs(x - y) for x, y in zip(a, p)) / len(a)


def wmean(vals, ws):
    tw = sum(ws)
    return sum(v * w for v, w in zip(vals, ws)) / tw if tw else 0.0


# ---------------------------------------------------------------------------
# stage: join + model + probe
# ---------------------------------------------------------------------------

MIN_CELL = 5   # minimum cohort size on BOTH sides for a usable cell


def build_panel(out_dir, min_cell=MIN_CELL, pool_years=False):
    """Join cohort cells to IPEDS cells. Returns (rows, attrition)."""
    by_cell, by_inst_year, by_inst = load_ipeds_cells(out_dir)
    coh = load_cohort_cells(out_dir)
    att = Counter()

    if pool_years:
        # collapse both sides over year -> immune to within-window date error
        pooled_c = defaultdict(Counter)
        for row in coh:
            k = (row["key"], row["unitid"], row["cip2"])
            for cat in CATEGORIES:
                pooled_c[k][cat] += int(row[cat])
        pooled_i = defaultdict(lambda: [0, 0])
        for (uid, cip2, _y), (t, n) in by_cell.items():
            pooled_i[(uid, cip2)][0] += t
            pooled_i[(uid, cip2)][1] += n
        coh2 = []
        for (key, uid, cip2), c in pooled_c.items():
            coh2.append({"key": key, "unitid": uid, "cip2": cip2, "year": 0,
                         "n": str(sum(c.values())),
                         **{cat: str(c.get(cat, 0)) for cat in CATEGORIES}})
        coh = coh2
        lookup = lambda r: pooled_i.get((r["unitid"], r["cip2"]))
    else:
        lookup = lambda r: by_cell.get((r["unitid"], r["cip2"], int(r["year"])))

    rows = []
    for r in coh:
        att["cohort_cells"] += 1
        n = int(r["n"])
        cell = lookup(r)
        if cell is None:
            att["drop_no_ipeds_cell"] += 1
            continue
        tot, nra = cell
        if tot < min_cell:
            att["drop_ipeds_cell_too_small"] += 1
            continue
        if n < min_cell:
            att["drop_cohort_too_small"] += 1
            continue
        counts = {cat: int(r[cat]) for cat in CATEGORIES}
        f = features_from_counts(counts, n)
        # Leave-one-out institution NRA share, straight from IPEDS. This is
        # the honest competitor: it is already public, needs no names, and
        # excludes the cell being predicted so there is no mechanical leakage.
        if pool_years:
            it, inr = by_inst.get(r["unitid"], (0, 0))
        else:
            it, inr = by_inst_year.get((r["unitid"], int(r["year"])), (0, 0))
        loo_t, loo_n = it - tot, inr - nra
        inst_nra = (loo_n / loo_t) if loo_t >= 10 else None
        if inst_nra is None:
            att["no_loo_inst_nra"] += 1
            inst_nra = 0.0
        att["matched"] += 1
        rows.append({
            "key": r["key"], "unitid": r["unitid"], "cip2": r["cip2"],
            "year": int(r["year"]), "n_ours": n, "ipeds_tot": tot,
            "ipeds_nra": nra, "y": nra / tot,
            "cov": n / tot, "inst_nra": inst_nra, **f,
        })
    return rows, dict(att)


def design(rows, feats, fe_fields=(), levels=None):
    """Build a design matrix: intercept + numeric feats + one-hot FE."""
    if levels is None:
        levels = {}
        for fld in fe_fields:
            levels[fld] = sorted({r[fld] for r in rows})[1:]  # drop first
    X = []
    for r in rows:
        row = [1.0] + [r[f] for f in feats]
        for fld in fe_fields:
            row += [1.0 if r[fld] == lv else 0.0 for lv in levels[fld]]
        X.append(row)
    return X, levels


def predict(X, b):
    return [sum(xi * bi for xi, bi in zip(row, b)) for row in X]


def grouped_cv(rows, feats, fe_fields=(), k=5, seed=7):
    """Hold out whole universities. Returns per-fold and pooled OOS R^2."""
    keys = sorted({r["key"] for r in rows})
    rnd = random.Random(seed)
    rnd.shuffle(keys)
    folds = [set(keys[i::k]) for i in range(k)]
    all_actual, all_pred, per_fold = [], [], []
    for f in folds:
        tr = [r for r in rows if r["key"] not in f]
        te = [r for r in rows if r["key"] in f]
        if not te or not tr:
            continue
        # fix FE levels from the training set so held-out universities
        # cannot introduce unseen columns
        Xtr, levels = design(tr, feats, fe_fields)
        b = ols(Xtr, [r["y"] for r in tr], ridge=1e-4)
        Xte, _ = design(te, feats, fe_fields, levels=levels)
        p = [min(1.0, max(0.0, v)) for v in predict(Xte, b)]
        a = [r["y"] for r in te]
        per_fold.append(r2(a, p))
        all_actual += a
        all_pred += p
    return (r2(all_actual, all_pred), per_fold,
            rmse(all_actual, all_pred), mae(all_actual, all_pred))


def baseline_cv(rows, k=5, seed=7):
    """Predict the training-set global mean NRA share for every held-out cell."""
    keys = sorted({r["key"] for r in rows})
    rnd = random.Random(seed)
    rnd.shuffle(keys)
    folds = [set(keys[i::k]) for i in range(k)]
    all_actual, all_pred, per_fold = [], [], []
    for f in folds:
        tr = [r for r in rows if r["key"] not in f]
        te = [r for r in rows if r["key"] in f]
        if not te or not tr:
            continue
        m = sum(r["y"] for r in tr) / len(tr)
        a = [r["y"] for r in te]
        p = [m] * len(te)
        per_fold.append(r2(a, p))
        all_actual += a
        all_pred += p
    return (r2(all_actual, all_pred), per_fold,
            rmse(all_actual, all_pred), mae(all_actual, all_pred))


def _fe_groups(rows, fe_fields):
    groups = []
    for fld in fe_fields:
        idx = defaultdict(list)
        for i, r in enumerate(rows):
            idx[r[fld]].append(i)
        groups.append(list(idx.values()))
    return groups


def residualize(rows, var, fe_fields, groups=None, iters=40, tol=1e-9):
    """Residuals of `var` after absorbing the given fixed effects, via
    alternating within-group demeaning (Frisch-Waugh). Equivalent to OLS on
    the dummy design but O(n) per sweep instead of O(n * p^2)."""
    v = [r[var] for r in rows]
    if groups is None:
        groups = _fe_groups(rows, fe_fields)
    for _ in range(iters):
        maxd = 0.0
        for g in groups:
            for members in g:
                m = sum(v[i] for i in members) / len(members)
                if abs(m) > maxd:
                    maxd = abs(m)
                for i in members:
                    v[i] -= m
        if maxd < tol:
            break
    return v


def fmt(v, nd=3):
    return "n/a" if v is None else f"{v:.{nd}f}"


def sd(vals):
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))


def cluster_bootstrap(rows, feat, fe_fields, reps=200, seed=11):
    """Resample whole universities with replacement; return (lo, hi) 95% CI
    for the raw correlation and for the FE-partial correlation."""
    keys = sorted({r["key"] for r in rows})
    by_key = defaultdict(list)
    for r in rows:
        by_key[r["key"]].append(r)
    rnd = random.Random(seed)
    raw, part = [], []
    for _ in range(reps):
        samp = []
        for i, k in enumerate(rnd.choices(keys, k=len(keys))):
            for r in by_key[k]:
                rr = dict(r)
                rr["key"] = f"{k}#{i}"
                samp.append(rr)
        ys = [r["y"] for r in samp]
        xs = [r[feat] for r in samp]
        c = pearson(xs, ys)
        if c is not None:
            raw.append(c)
        try:
            g = _fe_groups(samp, fe_fields)
            yr = residualize(samp, "y", fe_fields, groups=g)
            fr = residualize(samp, feat, fe_fields, groups=g)
            c2 = pearson(fr, yr)
            if c2 is not None:
                part.append(c2)
        except Exception:
            pass

    def ci(v):
        if len(v) < 20:
            return (None, None)
        v = sorted(v)
        return (v[int(0.025 * len(v))], v[int(0.975 * len(v)) - 1])
    return ci(raw), ci(part)


def sound_universities(out_dir, max_impossible=0.05, max_cv=0.5):
    dq = date_quality(out_dir)
    return {k for k, v in dq.items()
            if v["frac_impossible"] <= max_impossible
            and (v["cv"] is not None and v["cv"] <= max_cv)}


def stage_analyze(out_dir, min_cell=MIN_CELL, date_sound=False, pools=(False, True)):
    P = print
    keep = sound_universities(out_dir) if date_sound else None
    if keep is not None:
        P(f"[restricting to {len(keep)} date-sound universities]")

    for pool in pools:
        label = "POOLED OVER YEAR (date-error immune)" if pool else "BY YEAR"
        rows, att = build_panel(out_dir, min_cell=min_cell, pool_years=pool)
        if keep is not None:
            rows = [r for r in rows if r["key"] in keep]
        P(f"\n{'='*72}\n{label}  min_cell={min_cell}\n{'='*72}")
        P("join attrition: " + json.dumps(att))
        if not rows:
            continue
        P(f"matched cells: {len(rows)}  "
          f"universities: {len({r['key'] for r in rows})}  "
          f"fields: {len({r['cip2'] for r in rows})}")
        ys = [r["y"] for r in rows]
        P(f"NRA share: mean={fmt(sum(ys)/len(ys))} sd={fmt(sd(ys))}")
        covs = sorted(r["cov"] for r in rows)
        P(f"coverage (our n / IPEDS total): median={fmt(covs[len(covs)//2])} "
          f"p10={fmt(covs[len(covs)//10])} p90={fmt(covs[9*len(covs)//10])} "
          f"frac>1.5={fmt(sum(1 for c in covs if c > 1.5)/len(covs))}")

        P("\n-- raw correlations (n=%d cells) --" % len(rows))
        for f in FEATURE_NAMES:
            xs = [r[f] for r in rows]
            P(f"  {f:18s} pearson={fmt(pearson(xs, ys)):>7s} "
              f"spearman={fmt(spearman(xs, ys)):>7s}")

        P("\n-- partial correlation, controlling for institution+field+year --")
        fe = ["key", "cip2"] + ([] if pool else ["year"])
        fegroups = _fe_groups(rows, fe)
        yres = residualize(rows, "y", fe, groups=fegroups)
        for f in FEATURE_NAMES:
            fres = residualize(rows, f, fe, groups=fegroups)
            P(f"  {f:18s} partial_r={fmt(pearson(fres, yres)):>7s}")
        P(f"  (residual sd of y after FE: {fmt(sd(yres))} vs raw {fmt(sd(ys))})")

        P("\n-- held-out-by-university 5-fold CV, out-of-sample R^2 --")
        models = [
            ("M0 baseline: global train mean", None, ()),
            ("M1 name features only", FEATURE_NAMES, ()),
            ("M2 field FE only (no names)", [], ("cip2",)),
            ("M3 field FE + names", FEATURE_NAMES, ("cip2",)),
            ("M4 field+year FE + names", FEATURE_NAMES,
             ("cip2",) if pool else ("cip2", "year")),
            ("M5 sh_foreign_any only", ["sh_foreign_any"], ()),
            ("M6 sh_chinese only", ["sh_chinese"], ()),
            ("M7 field FE + IPEDS inst NRA (no names)", ["inst_nra"], ("cip2",)),
            ("M8 field FE + inst NRA + names",
             ["inst_nra"] + FEATURE_NAMES, ("cip2",)),
        ]
        for name, feats, fef in models:
            if feats is None:
                pooled, folds, rm, ma = baseline_cv(rows)
            else:
                pooled, folds, rm, ma = grouped_cv(rows, feats, fef)
            P(f"  {name:40s} R2={fmt(pooled):>7s} sd={fmt(sd(folds))} "
              f"RMSE={fmt(rm)} MAE={fmt(ma)}")

        P("\n-- cluster bootstrap (resample universities, 200 reps) --")
        (rlo, rhi), (plo, phi) = cluster_bootstrap(rows, "sh_foreign_any", fe)
        P(f"  raw r(sh_foreign_any, NRA):  95% CI [{fmt(rlo)}, {fmt(rhi)}]")
        P(f"  partial r after inst+field(+year) FE: "
          f"95% CI [{fmt(plo)}, {fmt(phi)}]")

        if pool:
            probe(rows, out_dir)


def probe(rows, out_dir):
    P = print
    P("\n-- within-university association (each university separately) --")
    by_key = defaultdict(list)
    for r in rows:
        by_key[r["key"]].append(r)
    rs = []
    for key, rr in sorted(by_key.items()):
        if len(rr) < 6:
            continue
        c = pearson([x["sh_foreign_any"] for x in rr], [x["y"] for x in rr])
        if c is not None:
            rs.append((c, key, len(rr)))
    rs.sort()
    P(f"  {len(rs)} universities with >=6 cells; "
      f"median within-university r = {fmt(rs[len(rs)//2][0]) if rs else 'n/a'}; "
      f"frac positive = {fmt(sum(1 for c,_,_ in rs if c>0)/len(rs)) if rs else 'n/a'}")
    P("  worst 3: " + ", ".join(f"{k}({n}) {c:.2f}" for c, k, n in rs[:3]))
    P("  best 3:  " + ", ".join(f"{k}({n}) {c:.2f}" for c, k, n in rs[-3:]))

    P("\n-- by field (CIP2) --")
    by_f = defaultdict(list)
    for r in rows:
        by_f[r["cip2"]].append(r)
    for cip2, rr in sorted(by_f.items(), key=lambda kv: -len(kv[1]))[:14]:
        c = pearson([x["sh_foreign_any"] for x in rr], [x["y"] for x in rr])
        ym = sum(x["y"] for x in rr) / len(rr)
        P(f"  {cip2} {CIP2_NAMES.get(cip2,'?'):22s} cells={len(rr):5d} "
          f"meanNRA={fmt(ym)} r={fmt(c)}")

    P("\n-- by cohort size (IPEDS total doctorates in the cell) --")
    bins = [(5, 9), (10, 24), (25, 49), (50, 10**6)]
    for lo, hi in bins:
        rr = [r for r in rows if lo <= r["ipeds_tot"] <= hi]
        if len(rr) < 10:
            continue
        c = pearson([x["sh_foreign_any"] for x in rr], [x["y"] for x in rr])
        P(f"  IPEDS total {lo}-{hi if hi < 10**6 else '+':>7}: cells={len(rr):5d} "
          f"r={fmt(c)}")

    P("\n-- by join quality (coverage ratio) --")
    for lo, hi, lbl in [(0.5, 1.5, "plausible 0.5-1.5"),
                        (0.0, 0.5, "under 0.5 (partial harvest)"),
                        (1.5, 10**6, "over 1.5 (impossible)")]:
        rr = [r for r in rows if lo <= r["cov"] < hi]
        if len(rr) < 10:
            continue
        c = pearson([x["sh_foreign_any"] for x in rr], [x["y"] for x in rr])
        P(f"  {lbl:32s} cells={len(rr):5d} r={fmt(c)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all",
                    choices=["all", "ipeds", "cohorts", "join", "datequal",
                             "analyze"])
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--min-cell", type=int, default=MIN_CELL)
    ap.add_argument("--date-sound", action="store_true",
                    help="restrict to universities whose record years pass "
                         "the IPEDS coverage-stability check")
    ap.add_argument("--pool", choices=["both", "year", "pooled"], default="both")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    if args.stage in ("all", "ipeds"):
        stage_ipeds(args.out)
    if args.stage in ("all", "cohorts"):
        stage_cohorts(args.out)
    if args.stage == "datequal":
        print(json.dumps(date_quality(args.out), indent=2))
    if args.stage in ("all", "analyze"):
        pools = {"both": (False, True), "year": (False,),
                 "pooled": (True,)}[args.pool]
        stage_analyze(args.out, min_cell=args.min_cell,
                      date_sound=args.date_sound, pools=pools)


if __name__ == "__main__":
    main()
