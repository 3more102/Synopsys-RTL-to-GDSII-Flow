#!/usr/bin/env python3
"""Auditable, dependency-free parsers for Synopsys-style QoR reports.

The module intentionally separates *parsing evidence* from engineering status.
A parsed value is not proof of signoff quality. Missing, malformed and conflicting
metrics remain explicit and are never converted to zero.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict
from typing import Any, Iterable

PARSER_VERSION = "2.0"
NUM = r"[+-]?(?:\d+(?:,\d{3})*(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"


@dataclass(frozen=True)
class Evidence:
    label: str
    line: int
    text: str
    source_value: float
    source_unit: str


@dataclass(frozen=True)
class Metric:
    value: float | int | None
    unit: str
    status: str
    evidence: tuple[Evidence, ...] = ()

    def json(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [asdict(x) for x in self.evidence]
        return data


UNIT_SCALE: dict[str, dict[str, tuple[float, str]]] = {
    "time": {
        "s": (1e9, "ns"), "ms": (1e6, "ns"), "us": (1e3, "ns"),
        "µs": (1e3, "ns"), "ns": (1.0, "ns"), "ps": (1e-3, "ns"), "fs": (1e-6, "ns"),
    },
    "power": {
        "w": (1.0, "W"), "mw": (1e-3, "W"), "uw": (1e-6, "W"),
        "µw": (1e-6, "W"), "nw": (1e-9, "W"), "pw": (1e-12, "W"),
    },
    "area": {
        "um2": (1.0, "um^2"), "um^2": (1.0, "um^2"), "µm2": (1.0, "um^2"),
        "µm^2": (1.0, "um^2"), "mm2": (1e6, "um^2"), "mm^2": (1e6, "um^2"),
    },
    "length": {
        "um": (1.0, "um"), "µm": (1.0, "um"), "mm": (1e3, "um"), "nm": (1e-3, "um"),
    },
    "ratio": {"": (1.0, "ratio"), "%": (0.01, "ratio")},
    "count": {"": (1.0, "count")},
    "scalar": {"": (1.0, "")},
}


def _unit_key(unit: str) -> str:
    return unit.strip().replace("²", "2").lower()


def parse_number(token: str) -> float:
    value = float(token.replace(",", ""))
    if not math.isfinite(value):
        raise ValueError(f"non-finite numeric token: {token}")
    return value


def normalize(value: float, unit: str, dimension: str, default_unit: str = "") -> tuple[float, str]:
    raw = unit.strip() or default_unit.strip()
    table = UNIT_SCALE[dimension]
    key = _unit_key(raw)
    if key not in table:
        raise ValueError(f"unsupported {dimension} unit: {raw or '<none>'}")
    scale, canonical = table[key]
    return value * scale, canonical


def _equivalent(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12)


def extract_metric(
    text: str,
    patterns: Iterable[tuple[str, str]],
    *,
    dimension: str = "scalar",
    default_unit: str = "",
    integer: bool = False,
) -> tuple[Metric, list[str]]:
    """Extract one metric with line-level evidence and conflict detection.

    Patterns must expose named group ``value`` and may expose ``unit``.
    Repeated equivalent values are accepted. Conflicting repeated summaries are
    deliberately not resolved by first/last-match heuristics.
    """
    matches: list[tuple[float, str, Evidence]] = []
    warnings: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, raw_pattern in patterns:
            match = re.search(raw_pattern, line, re.IGNORECASE)
            if not match:
                continue
            token = match.group("value")
            source_unit = (match.groupdict().get("unit") or "").strip()
            try:
                source_value = parse_number(token)
                canonical_value, canonical_unit = normalize(source_value, source_unit, dimension, default_unit)
            except ValueError as exc:
                warnings.append(f"line {lineno} {label}: {exc}")
                continue
            evidence = Evidence(label, lineno, line.strip()[:500], source_value, source_unit or default_unit)
            matches.append((canonical_value, canonical_unit, evidence))
            break
    if not matches:
        return Metric(None, UNIT_SCALE[dimension].get(_unit_key(default_unit), (1.0, default_unit))[1], "MISSING"), warnings
    first = matches[0][0]
    if any(not _equivalent(first, item[0]) for item in matches[1:]):
        warnings.append("conflicting repeated values: " + ", ".join(f"line {m[2].line}={m[0]:g}" for m in matches))
        return Metric(None, matches[0][1], "CONFLICT", tuple(m[2] for m in matches)), warnings
    value: float | int = int(round(first)) if integer and _equivalent(first, round(first)) else first
    return Metric(value, matches[0][1], "PARSED", tuple(m[2] for m in matches)), warnings


def _result(report_type: str, metrics: dict[str, Metric], warnings: list[str], context: dict[str, str] | None = None, **extra: Any) -> dict[str, Any]:
    statuses = {m.status for m in metrics.values()}
    if "CONFLICT" in statuses or any("malformed" in w.lower() for w in warnings):
        status = "PARSE_ERROR"
    elif statuses == {"MISSING"} or not metrics:
        status = "UNRECOGNIZED"
    elif "MISSING" in statuses:
        status = "PARTIAL"
    else:
        status = "PARSED"
    payload: dict[str, Any] = {
        "schema_version": 1,
        "parser": "rich_qor",
        "parser_version": PARSER_VERSION,
        "report_type": report_type,
        "status": status,
        "context": context or {},
        "metrics": {key: value.json() for key, value in metrics.items()},
        "warnings": warnings,
    }
    payload.update(extra)
    return payload


def parse_context(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    labels = {
        "scenario": r"^\s*(?:Scenario|Scenario Name)\s*[:=]\s*(\S.+?)\s*$",
        "mode": r"^\s*(?:Mode|Mode Name)\s*[:=]\s*(\S.+?)\s*$",
        "corner": r"^\s*(?:Corner|Corner Name|Operating Condition)\s*[:=]\s*(\S.+?)\s*$",
        "path_group": r"^\s*(?:Path Group|Group)\s*[:=]\s*(\S.+?)\s*$",
        "clock": r"^\s*(?:Clock|Clock Name)\s*[:=]\s*(\S.+?)\s*$",
    }
    for line in text.splitlines():
        for key, pattern in labels.items():
            m = re.search(pattern, line, re.IGNORECASE)
            if m and key not in out:
                out[key] = m.group(1).strip()
    return out


def _timing_metrics(text: str, analysis: str) -> tuple[dict[str, Metric], list[str]]:
    warnings: list[str] = []
    prefix = "setup" if analysis == "setup" else "hold"
    wns, w = extract_metric(text, [
        ("WNS", rf"\bWNS\b\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>fs|ps|ns|us|µs|ms|s)?"),
        ("Worst Negative Slack", rf"Worst\s+Negative\s+Slack\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>fs|ps|ns|us|µs|ms|s)?"),
        ("Critical Path Slack", rf"Critical\s+Path\s+Slack\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>fs|ps|ns|us|µs|ms|s)?"),
    ], dimension="time", default_unit="ns")
    warnings += w
    tns, w = extract_metric(text, [
        ("TNS", rf"\bTNS\b\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>fs|ps|ns|us|µs|ms|s)?"),
        ("Total Negative Slack", rf"Total\s+Negative\s+Slack\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>fs|ps|ns|us|µs|ms|s)?"),
    ], dimension="time", default_unit="ns")
    warnings += w
    viol, w = extract_metric(text, [
        ("Violating Paths", rf"(?:No\.\s*of\s+)?Violating\s+(?:Paths|Endpoints)\s*[:=]?\s*(?P<value>{NUM})"),
        ("Violation Count", rf"Violation\s+Count\s*[:=]?\s*(?P<value>{NUM})"),
    ], dimension="count", integer=True)
    warnings += w

    # Detailed report_timing fallback: use the worst explicit slack and count
    # violated path records only when summary fields are absent.
    slacks: list[tuple[float, Evidence, bool]] = []
    slack_re = re.compile(rf"\bslack\s*(?:\((?P<state>[^)]*)\))?\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>fs|ps|ns|us|µs|ms|s)?", re.I)
    for lineno, line in enumerate(text.splitlines(), 1):
        m = slack_re.search(line)
        if not m:
            continue
        try:
            raw = parse_number(m.group("value")); val, unit = normalize(raw, m.group("unit") or "", "time", "ns")
        except ValueError as exc:
            warnings.append(f"line {lineno} slack: {exc}"); continue
        state = (m.group("state") or "").upper()
        slacks.append((val, Evidence("slack", lineno, line.strip()[:500], raw, m.group("unit") or "ns"), "VIOLATED" in state or val < 0))
    if wns.status == "MISSING" and slacks:
        worst = min(slacks, key=lambda x: x[0])
        wns = Metric(worst[0], "ns", "PARSED", (worst[1],))
    if viol.status == "MISSING" and slacks:
        count = sum(1 for _, _, bad in slacks if bad)
        viol = Metric(count, "count", "PARSED", tuple(x[1] for x in slacks if x[2]))
    if tns.status == "MISSING" and slacks:
        negatives = [x[0] for x in slacks if x[0] < 0]
        if negatives:
            tns = Metric(sum(negatives), "ns", "PARSED", tuple(x[1] for x in slacks if x[0] < 0))
        elif slacks:
            tns = Metric(0.0, "ns", "PARSED", tuple(x[1] for x in slacks[:1]))
    status_value = None if wns.value is None else ("PASS" if float(wns.value) >= 0 and (viol.value in (None, 0)) else "FAIL")
    status_metric = Metric(None if status_value is None else (1 if status_value == "PASS" else 0), "boolean", "DERIVED")
    return {f"{prefix}_wns_ns": wns, f"{prefix}_tns_ns": tns, f"{prefix}_violations": viol, f"{prefix}_pass": status_metric}, warnings


def _scenario_sections(text: str) -> list[tuple[str, str]]:
    marks = list(re.finditer(r"(?im)^\s*(?:Scenario|Scenario Name)\s*[:=]\s*(\S.+?)\s*$", text))
    if not marks:
        return []
    sections: list[tuple[str, str]] = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        sections.append((mark.group(1).strip(), text[mark.start():end]))
    return sections


def parse_timing(text: str, analysis: str = "setup") -> dict[str, Any]:
    if analysis not in {"setup", "hold"}:
        raise ValueError("analysis must be 'setup' or 'hold'")
    metrics, warnings = _timing_metrics(text, analysis)
    scenarios = []
    for name, section in _scenario_sections(text):
        smetrics, swarnings = _timing_metrics(section, analysis)
        scenarios.append(_result("timing", smetrics, swarnings, {**parse_context(section), "scenario": name}, analysis=analysis))
    return _result("timing", metrics, warnings, parse_context(text), analysis=analysis, scenarios=scenarios)


def parse_area(text: str) -> dict[str, Any]:
    specs = {
        "total_cell_area_um2": ["Total cell area", "Total Cell Area"],
        "combinational_area_um2": ["Combinational area", "Combinational Cell Area"],
        "sequential_area_um2": ["Sequential area", "Noncombinational area", "Sequential Cell Area"],
        "macro_area_um2": ["Macro area", "Macro/Black Box area", "Black Box area"],
        "buffer_inverter_area_um2": ["Buffer/Inverter area", "Buf/Inv Area"],
    }
    metrics: dict[str, Metric] = {}; warnings: list[str] = []
    unit = r"(?P<unit>um2|um\^2|µm2|µm\^2|mm2|mm\^2)?"
    for key, labels in specs.items():
        pats = [(label, rf"{re.escape(label)}\s*[:=]?\s*(?P<value>{NUM})\s*{unit}") for label in labels]
        metrics[key], w = extract_metric(text, pats, dimension="area", default_unit="um2"); warnings += w
    count_specs = {
        "cell_count": ["Number of cells", "Cell Count", "Total Cell Count"],
        "combinational_cell_count": ["Combinational Cell Count", "Combinational cells"],
        "sequential_cell_count": ["Sequential Cell Count", "Sequential cells", "Noncombinational cells"],
        "macro_count": ["Macro Count", "Black Box Count"],
        "buffer_count": ["Buffer Count", "Buffers"],
        "inverter_count": ["Inverter Count", "Inverters"],
    }
    for key, labels in count_specs.items():
        metrics[key], w = extract_metric(text, [(label, rf"{re.escape(label)}\s*[:=]?\s*(?P<value>{NUM})") for label in labels], dimension="count", integer=True); warnings += w
    metrics["utilization_ratio"], w = extract_metric(text, [
        ("Utilization Ratio", rf"Utilization\s+(?:Ratio|%)?\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>%)?"),
        ("Cell Utilization", rf"Cell\s+Utilization\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>%)?"),
    ], dimension="ratio"); warnings += w
    return _result("area", metrics, warnings, parse_context(text))


def parse_power_detail(text: str) -> dict[str, Any]:
    metrics: dict[str, Metric] = {}; warnings: list[str] = []
    unit = r"(?P<unit>pW|nW|uW|µW|mW|W)?"
    labels = {
        "internal_w": ["Internal Power", "Cell Internal Power"],
        "switching_w": ["Switching Power", "Net Switching Power"],
        "leakage_w": ["Leakage Power", "Cell Leakage Power"],
        "total_w": ["Total Power"],
    }
    for key, names in labels.items():
        metrics[key], w = extract_metric(text, [(name, rf"{re.escape(name)}\s*[:=]?\s*(?P<value>{NUM})\s*{unit}") for name in names], dimension="power", default_unit="W"); warnings += w
    # Common report_power total row: Total <internal> <switching> <leakage> <total> <unit>
    if all(metrics[k].status == "MISSING" for k in ("internal_w", "switching_w", "leakage_w", "total_w")):
        table = re.compile(rf"(?im)^\s*Total\s+(?P<i>{NUM})\s+(?P<s>{NUM})\s+(?P<l>{NUM})\s+(?P<t>{NUM})\s*(?P<u>pW|nW|uW|µW|mW|W)\s*$")
        m = table.search(text)
        if m:
            for key, group, label in (("internal_w", "i", "Total/internal"), ("switching_w", "s", "Total/switching"), ("leakage_w", "l", "Total/leakage"), ("total_w", "t", "Total/total")):
                raw = parse_number(m.group(group)); val, canonical = normalize(raw, m.group("u"), "power")
                line = text[:m.start()].count("\n") + 1
                metrics[key] = Metric(val, canonical, "PARSED", (Evidence(label, line, m.group(0).strip(), raw, m.group("u")),))
    return _result("power", metrics, warnings, parse_context(text))


def parse_cts(text: str) -> dict[str, Any]:
    metrics: dict[str, Metric] = {}; warnings: list[str] = []
    for key, labels in {
        "clock_skew_ns": ["Clock Skew", "Global Skew", "Worst Skew"],
        "source_latency_ns": ["Source Latency"], "network_latency_ns": ["Network Latency"],
        "total_latency_ns": ["Total Latency", "Clock Latency"], "max_transition_ns": ["Max Transition", "Maximum Transition"],
    }.items():
        metrics[key], w = extract_metric(text, [(label, rf"{re.escape(label)}\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>fs|ps|ns|us|µs|ms|s)?") for label in labels], dimension="time", default_unit="ns"); warnings += w
    for key, labels in {
        "sink_count": ["Sink Count", "Number of Sinks"], "buffer_count": ["Buffer Count", "Clock Buffers"],
        "inverter_count": ["Inverter Count", "Clock Inverters"], "clock_cell_count": ["Clock Cell Count", "Clock Cells"],
        "tree_levels": ["Clock Tree Levels", "Tree Levels"],
    }.items():
        metrics[key], w = extract_metric(text, [(label, rf"{re.escape(label)}\s*[:=]?\s*(?P<value>{NUM})") for label in labels], dimension="count", integer=True); warnings += w
    return _result("cts", metrics, warnings, parse_context(text))


def parse_route(text: str) -> dict[str, Any]:
    metrics: dict[str, Metric] = {}; warnings: list[str] = []
    for key, labels in {
        "drc_violations": ["DRC violations", "Total number of violations", "Violation Count"],
        "via_count": ["Via Count", "Total Vias"], "short_count": ["Short Count", "Shorts"],
        "open_count": ["Open Count", "Opens"], "congested_bins": ["Congested Bins"],
    }.items():
        metrics[key], w = extract_metric(text, [(label, rf"{re.escape(label)}\s*[:=]?\s*(?P<value>{NUM})") for label in labels], dimension="count", integer=True); warnings += w
    metrics["wire_length_um"], w = extract_metric(text, [
        ("Total Wire Length", rf"Total\s+Wire\s+Length\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>nm|um|µm|mm)?"),
        ("Wire Length", rf"Wire\s+Length\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>nm|um|µm|mm)?"),
    ], dimension="length", default_unit="um"); warnings += w
    for key, labels in {
        "congestion_ratio": ["Global Route Congestion", "Routing Congestion"],
        "horizontal_overflow": ["Horizontal Overflow"], "vertical_overflow": ["Vertical Overflow"],
        "max_overflow": ["Max Overflow", "Maximum Overflow"], "total_overflow": ["Total Overflow", "Congestion Overflow"],
    }.items():
        metrics[key], w = extract_metric(text, [(label, rf"{re.escape(label)}\s*[:=]?\s*(?P<value>{NUM})\s*(?P<unit>%)?") for label in labels], dimension="ratio"); warnings += w
    return _result("route", metrics, warnings, parse_context(text))


def parse_physical_verification(text: str, kind: str = "drc") -> dict[str, Any]:
    kind = kind.lower()
    if kind not in {"drc", "lvs", "antenna", "density"}:
        raise ValueError(f"unsupported physical verification kind: {kind}")
    warnings: list[str] = []; metrics: dict[str, Metric] = {}
    label_map = {
        "drc": ("violations", ["DRC violations", "Total number of violations", "Violation Count"]),
        "lvs": ("mismatch_count", ["LVS mismatch count", "Mismatch Count", "Total mismatches"]),
        "antenna": ("violations", ["Antenna violations", "Antenna Violation Count"]),
        "density": ("violations", ["Density violations", "Density Violation Count"]),
    }
    metric_key, labels = label_map[kind]
    metrics[metric_key], w = extract_metric(text, [(label, rf"{re.escape(label)}\s*[:=]?\s*(?P<value>{NUM})") for label in labels], dimension="count", integer=True); warnings += w
    explicit_pass = bool(re.search(rf"(?im)^\s*{kind}\s+(?:result\s*[:=]\s*)?(?:PASS|CLEAN|MATCH(?:ED)?)\s*$", text))
    explicit_fail = bool(re.search(rf"(?im)^\s*{kind}\s+(?:result\s*[:=]\s*)?(?:FAIL|FAILED|MISMATCH)\s*$", text))
    count = metrics[metric_key].value
    if explicit_fail or (count is not None and int(count) > 0): result_status = "FAIL"
    elif explicit_pass or count == 0: result_status = "PASS"
    elif not text.strip(): result_status = "NOT_RUN"
    elif metrics[metric_key].status == "CONFLICT": result_status = "PARSE_ERROR"
    else: result_status = "UNKNOWN"
    return _result(kind, metrics, warnings, parse_context(text), result_status=result_status)


def metric_value(result: dict[str, Any], key: str) -> Any:
    metric = result.get("metrics", {}).get(key, {})
    return metric.get("value") if isinstance(metric, dict) else None
