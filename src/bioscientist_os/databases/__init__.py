"""Offline-first database connector layer (Milestone 6).

A base connector interface with a required fixture-backed adapter, a gitignored
cache layer under ``data/cache/``, and optional live connectors that are off by
default and never required for tests. Every record records its provenance
(fixture / cache / live). Empty at Milestone 0.
"""

from __future__ import annotations
