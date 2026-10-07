# Modified/added 2026-10-07 for this unofficial GPL-3.0-only application.
# Upstream MIT portions retain their notices in LICENSES/Jev-MIT.txt.
"""Ephemeral profiles; a new observed conversation requires confirmation."""
from copy import deepcopy

class AdvisorSessions:
    def __init__(self):
        self.profiles = {}
        self.confirmed = None

    def leave(self):
        self.confirmed = None

    def activate(self, title, profile):
        if not title:
            raise ValueError('请先打开具体会话')
        self.profiles[title] = deepcopy(profile)
        self.confirmed = title

    def get(self, title):
        if self.confirmed != title:
            return None
        return deepcopy(self.profiles.get(title))

    def forget(self, title):
        self.profiles.pop(title, None)
        self.confirmed = None
