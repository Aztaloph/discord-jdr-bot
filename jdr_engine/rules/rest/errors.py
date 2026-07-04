# jdr_engine/rules/rest/errors.py
"""Erreurs métier — repos long / court (SRD 2014)."""


class RestError(Exception):
    """Repos impossible ou règle SRD violée."""
