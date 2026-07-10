"""Deterministic grading logic for ResumeExtractBench.
Ports grading metrics from longextract-bench and adds field-level diff tracing.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any, Dict, List, Tuple, Optional

Json = Any

_PLACEHOLDERS = {"", "..", "...", "-", "--", "n/a", "na", "none", "null"}

def canonical(v: Json) -> str:
    """Canonicalize a value to normalize cosmetic differences."""
    if v is None or v == [] or v == {}:
        return ""
    s = str(v).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("µ", "u").replace("μ", "u")
    s = re.sub(r"\s*\[\s*(?:\d{1,2}|[a-z])\s*\]", "", s)
    for a, b in (
        ("’", "'"),
        ("‘", "'"),
        ("“", '"'),
        ("”", '"'),
        ("–", "-"),
        ("—", "-"),
    ):
        s = s.replace(a, b)
    num = s.replace(",", "").replace("$", "").replace("%", "")
    try:
        f = float(num)
        return str(int(f)) if f == int(f) else str(f)
    except ValueError:
        pass
    if re.sub(r"\s+", " ", s) in _PLACEHOLDERS:
        return ""
    s = re.sub(r"[\s,\-.]", "", s)
    return re.sub(r"\d+", lambda m: str(int(m.group())), s)

def unwrap(o: Json) -> Json:
    """Strip a {value, citations} envelope recursively."""
    if isinstance(o, dict):
        if "value" in o and ("citations" in o or "confidence" in o) and len(o) <= 6:
            return unwrap(o["value"])
        return {k: unwrap(v) for k, v in o.items()}
    if isinstance(o, list):
        return [unwrap(x) for x in o]
    return o

def _scalar_field_names(rows: List[Dict[str, Json]]) -> set[str]:
    names: set[str] = set()
    for r in rows:
        if isinstance(r, dict):
            for k, v in r.items():
                if not isinstance(v, (dict, list)):
                    names.add(k)
    return names

def infer_row_key(
    rows_p: List[Dict[str, Json]], rows_g: List[Dict[str, Json]]
) -> List[str]:
    """Infer matching key columns for row arrays from the data."""
    if not rows_p or not rows_g:
        return []
    fields = sorted(_scalar_field_names(rows_p) | _scalar_field_names(rows_g))

    def usable(field: str, rows: List[Dict[str, Json]]) -> bool:
        vals = [r.get(field) for r in rows if isinstance(r, dict)]
        non_null = [v for v in vals if canonical(v) != ""]
        if len(non_null) < 0.8 * len(rows):
            return False
        return len({canonical(v) for v in non_null}) / len(non_null) >= 0.5

    def match_rate(field: str) -> float:
        bvals = {canonical(r.get(field)) for r in rows_g if isinstance(r, dict) and canonical(r.get(field))}
        hit = sum(1 for r in rows_p if isinstance(r, dict) and canonical(r.get(field)) in bvals)
        return hit / max(len(rows_p), 1)

    def non_null_rate(field: str, rows: List[Dict[str, Json]]) -> float:
        return sum(1 for r in rows if isinstance(r, dict) and canonical(r.get(field)) != "") / max(len(rows), 1)

    def uniqueness(flds: List[str], rows: List[Dict[str, Json]]) -> float:
        combos = {tuple(canonical(r.get(f)) for f in flds) for r in rows if isinstance(r, dict)}
        return len(combos) / max(len(rows), 1)

    gt_usable = [f for f in fields if usable(f, rows_g)]
    if gt_usable:
        return [max(gt_usable, key=lambda f: (uniqueness([f], rows_g), match_rate(f)))]

    dims = [f for f in fields if non_null_rate(f, rows_g) >= 0.8]
    selected: List[str] = []
    remaining = list(dims)
    while remaining and len(selected) < 4:
        nxt = max(remaining, key=lambda f: uniqueness([*selected, f], rows_g))
        selected.append(nxt)
        remaining.remove(nxt)
        if uniqueness(selected, rows_g) >= 0.95:
            return selected
    return []

def _rowkey(row: Dict[str, Json], kf: List[str], idx: int) -> Tuple[Any, ...]:
    if not kf:
        return ("__idx__", idx)
    return tuple(canonical(row.get(f)) for f in kf)

def _count_leaves(v: Json) -> int:
    if isinstance(v, dict):
        return sum(_count_leaves(x) for x in v.values())
    if isinstance(v, list):
        return sum(_count_leaves(x) for x in v)
    return 0 if v is None else 1

def _canon_sig(v: Json) -> Any:
    if isinstance(v, dict):
        return ("d", tuple(sorted((k, _canon_sig(x)) for k, x in v.items())))
    if isinstance(v, list):
        return ("l", tuple(sorted(repr(_canon_sig(x)) for x in v)))
    return canonical(v)

_GREEDY_CAP = 4000

def _pair_bucket(
    prs: List[Dict[str, Json]], grs: List[Dict[str, Json]]
) -> Tuple[List[Tuple[Dict[str, Json], Dict[str, Json]]], List[Dict[str, Json]], List[Dict[str, Json]]]:
    gsig: Dict[Any, List[Dict[str, Json]]] = {}
    for r in grs:
        gsig.setdefault(_canon_sig(r), []).append(r)
    pairs: List[Tuple[Dict[str, Json], Dict[str, Json]]] = []
    res_p: List[Dict[str, Json]] = []
    for pr in prs:
        bucket = gsig.get(_canon_sig(pr))
        if bucket:
            pairs.append((pr, bucket.pop()))
        else:
            res_p.append(pr)
    res_g = [r for rs in gsig.values() for r in rs]
    if not res_p or not res_g:
        return pairs, res_p, res_g
    if len(res_p) * len(res_g) > _GREEDY_CAP:
        n = min(len(res_p), len(res_g))
        pairs += list(zip(res_p[:n], res_g[:n]))
        return pairs, res_p[n:], res_g[n:]
    gpool = list(res_g)
    up: List[Dict[str, Json]] = []
    for pr in res_p:
        if not gpool:
            up.append(pr)
            continue
        j = max(range(len(gpool)), key=lambda k: grade_value(pr, gpool[k])[1])
        pairs.append((pr, gpool.pop(j)))
    return pairs, up, gpool

def _match_rows(
    p: List[Dict[str, Json]], g: List[Dict[str, Json]], kf: List[str]
) -> Tuple[List[Tuple[Dict[str, Json], Dict[str, Json]]], List[Dict[str, Json]], List[Dict[str, Json]]]:
    if not kf:
        return _pair_bucket(list(p), list(g))
    gb: Dict[Tuple[Any, ...], List[Dict[str, Json]]] = {}
    for i, r in enumerate(g):
        gb.setdefault(_rowkey(r, kf, i), []).append(r)
    pb: Dict[Tuple[Any, ...], List[Dict[str, Json]]] = {}
    for i, r in enumerate(p):
        pb.setdefault(_rowkey(r, kf, i), []).append(r)
    pairs: List[Tuple[Dict[str, Json], Dict[str, Json]]] = []
    up: List[Dict[str, Json]] = []
    ug: List[Dict[str, Json]] = []
    for k in set(gb) | set(pb):
        kp, kup, kug = _pair_bucket(pb.get(k, []), gb.get(k, []))
        pairs += kp
        up += kup
        ug += kug
    return pairs, up, kug

def grade_value(pv: Json, gv: Json) -> Tuple[int, int]:
    """Recursively grade two values -> (leaf_total, leaf_match)."""
    if isinstance(pv, dict) or isinstance(gv, dict):
        pv = pv if isinstance(pv, dict) else {}
        gv = gv if isinstance(gv, dict) else {}
        t = m = 0
        for k in set(pv) | set(gv):
            tt, mm = grade_value(pv.get(k), gv.get(k))
            t += tt
            m += mm
        return t, m
    if isinstance(pv, list) or isinstance(gv, list):
        pv = pv if isinstance(pv, list) else []
        gv = gv if isinstance(gv, list) else []
        pd = [x for x in pv if isinstance(x, dict)]
        gd = [x for x in gv if isinstance(x, dict)]
        if pd or gd:
            pairs, up, ug = _match_rows(pd, gd, infer_row_key(pd, gd))
            t = m = 0
            for prow, grow in pairs:
                tt, mm = grade_value(prow, grow)
                t += tt
                m += mm
            for prow in up:
                t += _count_leaves(prow)
            for grow in ug:
                t += _count_leaves(grow)
            return t, m
        cp = Counter(canonical(x) for x in pv)
        cg = Counter(canonical(x) for x in gv)
        return max(sum(cp.values()), sum(cg.values())), sum((cp & cg).values())
    if pv is None and gv is None:
        return 0, 0
    return 1, int(canonical(pv) == canonical(gv))

def _arrays(schema: Dict[str, Json]) -> List[str]:
    out: List[str] = []
    for k, v in schema.get("properties", {}).items():
        if isinstance(v, dict):
            t = v.get("type")
            if t == "array" or (isinstance(t, list) and "array" in t):
                out.append(k)
    return out

def walk_diff(pv: Any, gv: Any, schema_prop: Dict[str, Any], path: str, diffs: List[Dict[str, Any]]) -> None:
    """Recursively walks the schema to log field_diffs."""
    if not isinstance(schema_prop, dict):
        return

    prop_type = schema_prop.get("type")

    # If the schema type is an object
    if prop_type == "object" or "properties" in schema_prop:
        pv_dict = pv if isinstance(pv, dict) else {}
        gv_dict = gv if isinstance(gv, dict) else {}
        properties = schema_prop.get("properties", {})
        for k, sub_schema in properties.items():
            sub_path = f"{path}.{k}" if path else k
            walk_diff(pv_dict.get(k), gv_dict.get(k), sub_schema, sub_path, diffs)
        return

    # If the schema type is an array
    if prop_type == "array" or "items" in schema_prop:
        pv_list = pv if isinstance(pv, list) else []
        gv_list = gv if isinstance(gv, list) else []
        items_schema = schema_prop.get("items", {})
        
        # Check if array contains objects
        is_obj_array = items_schema.get("type") == "object" or "properties" in items_schema

        if is_obj_array:
            pd = [r for r in pv_list if isinstance(r, dict)]
            gd = [r for r in gv_list if isinstance(r, dict)]
            pairs, up, ug = _match_rows(pd, gd, infer_row_key(pd, gd))
            
            # Map matched rows
            for prow, grow in pairs:
                # Find index in ground truth array
                try:
                    idx = gd.index(grow)
                except ValueError:
                    idx = 0
                sub_path = f"{path}[{idx}]"
                walk_diff(prow, grow, items_schema, sub_path, diffs)
            
            # Map missed rows
            for grow in ug:
                try:
                    idx = gd.index(grow)
                except ValueError:
                    idx = 0
                sub_path = f"{path}[{idx}]"
                walk_diff(None, grow, items_schema, sub_path, diffs)
                
            # Map hallucinated rows
            for j, prow in enumerate(up):
                sub_path = f"{path}[{len(gd) + j}]"
                walk_diff(prow, None, items_schema, sub_path, diffs)
        else:
            # Array of scalars
            # Multiset pairing
            gd_items = list(gv_list)
            pd_items = list(pv_list)
            
            # To preserve index mappings, we first match exact or canonical elements
            matched_p_indices = set()
            
            for i, gt_val in enumerate(gd_items):
                gt_canon = canonical(gt_val)
                found = False
                for j, pred_val in enumerate(pd_items):
                    if j not in matched_p_indices and canonical(pred_val) == gt_canon:
                        matched_p_indices.add(j)
                        diffs.append({
                            "path": f"{path}[{i}]",
                            "status": "correct",
                            "predicted": pred_val,
                            "ground_truth": gt_val
                        })
                        found = True
                        break
                if not found:
                    diffs.append({
                        "path": f"{path}[{i}]",
                        "status": "missed",
                        "predicted": None,
                        "ground_truth": gt_val
                    })
            
            # Unmatched predictions are hallucinated
            for j, pred_val in enumerate(pd_items):
                if j not in matched_p_indices:
                    diffs.append({
                        "path": f"{path}[{len(gd_items) + j}]",
                        "status": "hallucinated",
                        "predicted": pred_val,
                        "ground_truth": None
                    })
        return

    # Scalar comparison
    pv_canon = canonical(pv)
    gv_canon = canonical(gv)

    if pv_canon == "" and gv_canon == "":
        # Both empty, no meaningful mismatch to report, but let's record as correct
        # if both fields are defined in prediction or ground truth
        if pv is not None or gv is not None:
            diffs.append({
                "path": path,
                "status": "correct",
                "predicted": pv,
                "ground_truth": gv
            })
    elif pv_canon != "" and gv_canon == "":
        diffs.append({
            "path": path,
            "status": "hallucinated",
            "predicted": pv,
            "ground_truth": gv
        })
    elif gv_canon != "" and pv_canon == "":
        diffs.append({
            "path": path,
            "status": "missed",
            "predicted": pv,
            "ground_truth": gv
        })
    else:
        if pv_canon == gv_canon:
            diffs.append({
                "path": path,
                "status": "correct",
                "predicted": pv,
                "ground_truth": gv
            })
        else:
            diffs.append({
                "path": path,
                "status": "incorrect",
                "predicted": pv,
                "ground_truth": gv
            })

def grade(
    schema: dict, predicted: dict, ground_truth: dict
) -> dict[str, Any]:
    """Score the predicted output against the ground truth answer key under the schema.

    Returns:
        {leaf_accuracy, precision, recall, completed: bool, failure_reason: str|None, field_diffs: list}
    """
    if predicted is None or not isinstance(predicted, dict) or not predicted:
        return {
            "leaf_accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "completed": False,
            "failure_reason": "Predicted output is missing or is not a valid JSON object",
            "field_diffs": []
        }

    if ground_truth is None or not isinstance(ground_truth, dict):
        return {
            "leaf_accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "completed": False,
            "failure_reason": "Ground truth is missing or is not a valid JSON object",
            "field_diffs": []
        }

    try:
        # Unwrap envelopes if present
        pred_unwrapped = unwrap(predicted)
        gt_unwrapped = unwrap(ground_truth)

        # 1. Compute deterministic scores
        arr_keys = _arrays(schema)
        gt_rows = pred_rows = matched = 0
        leaf_total = leaf_match = base_total = base_match = 0

        for arr in arr_keys:
            g = [r for r in (gt_unwrapped.get(arr, []) or []) if isinstance(r, dict)]
            p = [r for r in (pred_unwrapped.get(arr, []) or []) if isinstance(r, dict)]
            gt_rows += len(g)
            pred_rows += len(p)
            if not g and not p:
                continue
            pairs, _up, _ug = _match_rows(p, g, infer_row_key(p, g))
            for prow, grow in pairs:
                tt, mm = grade_value(prow, grow)
                matched += 1
                leaf_total += tt
                leaf_match += mm

        for k in (set(gt_unwrapped) | set(pred_unwrapped)) - set(arr_keys):
            tt, mm = grade_value(pred_unwrapped.get(k), gt_unwrapped.get(k))
            base_total += tt
            base_match += mm

        tot_leaf = leaf_total + base_total
        tot_match = leaf_match + base_match

        precision = matched / pred_rows if pred_rows else (1.0 if not gt_rows else 0.0)
        recall = matched / gt_rows if gt_rows else (1.0 if not pred_rows else 0.0)
        leaf_accuracy = (tot_match / tot_leaf) if tot_leaf else (1.0 if not (set(gt_unwrapped) | set(pred_unwrapped)) else 0.0)

        # 2. Trace diffs
        field_diffs = []
        walk_diff(pred_unwrapped, gt_unwrapped, schema, "", field_diffs)

        return {
            "leaf_accuracy": round(leaf_accuracy * 100, 2),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "leaf_total": tot_leaf,
            "leaf_match": tot_match,
            "completed": True,
            "failure_reason": None,
            "field_diffs": field_diffs
        }
    except Exception as e:
        return {
            "leaf_accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "completed": False,
            "failure_reason": f"Exception during grading: {str(e)}",
            "field_diffs": []
        }
