# Modified/added 2026-10-07 for this unofficial GPL-3.0-only application.
# Upstream MIT portions retain their notices in LICENSES/Jev-MIT.txt.
"""Unofficial source snapshot: upstream binary update checks are disabled.
Modified 2026-10-07. Distributed as part of this application under GPL-3.0-only.
Original upstream portions retain their MIT terms; see LICENSES/Jev-MIT.txt.
"""
def parse_version(v):
    parts = v.split('.')
    return tuple(map(int, parts)) if parts and all(p.isdigit() for p in parts) else None

def check_latest(current, timeout=6):
    return None
