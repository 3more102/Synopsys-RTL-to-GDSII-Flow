#!/usr/bin/env python3
"""Compatibility facade over the auditable rich QoR parser stack.

Legacy callers keep receiving the same tuple/scalar API. New code should import
``rich_qor`` and consume structured metrics/evidence directly.
"""
from __future__ import annotations

from rich_qor import (
    metric_value,
    parse_area,
    parse_cts,
    parse_physical_verification,
    parse_power_detail,
    parse_route,
    parse_timing,
)


def parse_qor(s: str):
    result = parse_timing(s, "setup")
    return (
        metric_value(result, "setup_wns_ns"),
        metric_value(result, "setup_tns_ns"),
        metric_value(result, "setup_violations"),
    )


def parse_area_util(s: str):
    result = parse_area(s)
    return (
        metric_value(result, "total_cell_area_um2"),
        metric_value(result, "utilization_ratio"),
        metric_value(result, "cell_count"),
    )


def parse_power(s: str):
    return metric_value(parse_power_detail(s), "total_w")


def parse_congestion(s: str):
    result = parse_route(s)
    total = metric_value(result, "total_overflow")
    return total if total is not None else metric_value(result, "congestion_ratio")


def parse_drc(s: str):
    route = parse_route(s)
    value = metric_value(route, "drc_violations")
    if value is not None:
        return value
    return metric_value(parse_physical_verification(s, "drc"), "violations")


__all__ = [
    "parse_qor",
    "parse_area_util",
    "parse_power",
    "parse_congestion",
    "parse_drc",
    "parse_timing",
    "parse_area",
    "parse_power_detail",
    "parse_cts",
    "parse_route",
    "parse_physical_verification",
]
