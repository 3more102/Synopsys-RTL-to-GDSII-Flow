#!/usr/bin/env python3
"""Pure report parsers used by QoR summarization and unit tests.

The functions return None when a metric cannot be proven from text. They never
invent defaults, units, or signoff values.
"""
from __future__ import annotations
from report_utils import first_float, first_int


def parse_qor(s: str):
    return (
        first_float([
            r'Critical Path Slack\s*[:=]?\s*(-?[\d.]+)',
            r'\bWNS\s*[:=]?\s*(-?[\d.]+)',
            r'Worst Negative Slack\s*[:=]?\s*(-?[\d.]+)',
        ], s),
        first_float([
            r'Total Negative Slack\s*[:=]?\s*(-?[\d.]+)',
            r'\bTNS\s*[:=]?\s*(-?[\d.]+)',
        ], s),
        first_int([
            r'No\. of Violating Paths\s*[:=]?\s*(\d+)',
            r'violating\s+(?:paths|endpoints)\s*[:=]?\s*(\d+)',
        ], s),
    )


def parse_area_util(s: str):
    area = first_float([
        r'Total\s+cell\s+area\s*:\s*([\d.eE+-]+)',
        r'Total\s+Cell\s+Area\s*[:=]\s*([\d.eE+-]+)',
    ], s)
    util = first_float([
        r'Utilization\s*(?:Ratio|%)?\s*[:=]?\s*([\d.]+)',
        r'Cell\s+Utilization\s*[:=]?\s*([\d.]+)',
    ], s)
    cells = first_int([
        r'Number\s+of\s+cells\s*:\s*(\d+)',
        r'Cell\s+Count\s*[:=]\s*(\d+)',
    ], s)
    return area, util, cells


def parse_power(s: str):
    return first_float([r'Total\s+Power\s*[:=]?\s*([\d.eE+-]+)'], s)


def parse_congestion(s: str):
    return first_float([
        r'Total\s+Overflow\s*[:=]?\s*([\d.]+)',
        r'Global\s+Route\s+Congestion\s*[:=]?\s*([\d.]+)',
        r'Congestion\s+Overflow\s*[:=]?\s*([\d.]+)',
    ], s)


def parse_drc(s: str):
    return first_int([
        r'Total\s+(?:number\s+of\s+)?violations\s*[:=]?\s*(\d+)',
        r'DRC\s+violations\s*[:=]?\s*(\d+)',
        r'Violation\s+Count\s*[:=]?\s*(\d+)',
    ], s)
