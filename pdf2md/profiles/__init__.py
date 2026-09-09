# -*- coding: utf-8 -*-
"""Profile registry.  Add a new document kind by importing it here."""
from .base import Profile
from .visk import ViskProfile

ALL = [ViskProfile, Profile]


def pick(doc):
    """Choose the profile that best fits the document."""
    scored = sorted(((p.score(doc), p) for p in ALL), key=lambda t: -t[0])
    best_score, best = scored[0]
    return best(), best_score

__all__ = ["ALL", "Profile", "ViskProfile", "pick"]
