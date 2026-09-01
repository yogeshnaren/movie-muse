"""Local-first persistence (MM-004).

The embedded store is authoritative on device. Editor JSON is never a
persistence contract; only typed ``ScreenplayDocument`` snapshots are stored.
"""

from __future__ import annotations
