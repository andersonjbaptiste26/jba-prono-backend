"""
Cache mémoire (RAM) pour JBa Prono.

- TTL (Time To Live) configurable par route
- Thread-safe (Lock)
- Clé calculée automatiquement (ignore db/request/dependencies)
- Invalidation manuelle via `cache_invalidate(prefix)`
- Helper `match_still_visible` : filtre les matchs > 5 min après le coup d'envoi
"""
import time
import threading
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import Any, Callable, Optional

_cache: dict[str, tuple[float, Any]] = {}
_lock = threading.Lock()

_IGNORED_ARG_NAMES = {
    "db", "request", "response", "background_tasks",
    "user_id", "_", "current_user", "session",
}

# Fenêtre de grâce après le coup d'envoi pendant laquelle un match reste affiché
MATCH_GRACE_MINUTES = 5


def _default_key_fn(args: tuple, kwargs: dict, prefix: str) -> str:
    parts = [prefix]
    for k in sorted(kwargs.keys()):
        if k in _IGNORED_ARG_NAMES:
            continue
        v = kwargs[k]
        if isinstance(v, (int, str, float, bool)) or v is None:
            parts.append(f"{k}={v}")
    for a in args:
        if isinstance(a, (int, str, float, bool)) or a is None:
            parts.append(str(a))
    return "|".join(parts)


def cached(ttl_seconds: int = 300, prefix: Optional[str] = None,
           key_fn: Optional[Callable] = None):
    """Décorateur de mise en cache TTL."""
    def decorator(func: Callable):
        p = prefix or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            kf = key_fn or _default_key_fn
            key = kf(args, kwargs, p)
            now = time.time()

            with _lock:
                entry = _cache.get(key)
                if entry and entry[0] > now:
                    return entry[1]
                if entry:
                    del _cache[key]

            result = func(*args, **kwargs)

            with _lock:
                _cache[key] = (now + ttl_seconds, result)

            return result

        wrapper._cache_prefix = p
        wrapper._cache_ttl = ttl_seconds
        return wrapper
    return decorator


def cache_invalidate(prefix: Optional[str] = None) -> int:
    """Vide le cache. Si `prefix`, ne supprime que les clés correspondantes."""
    with _lock:
        if prefix is None:
            n = len(_cache)
            _cache.clear()
            return n
        keys = [k for k in _cache.keys() if k.startswith(prefix)]
        for k in keys:
            del _cache[k]
        return len(keys)


def cache_stats() -> dict:
    """Debug : nombre d'entrées vivantes/expirées."""
    with _lock:
        now = time.time()
        total = len(_cache)
        alive = sum(1 for exp, _ in _cache.values() if exp > now)
        return {
            "total_entries": total,
            "alive_entries": alive,
            "expired_entries": total - alive,
        }


def match_still_visible(match) -> bool:
    """
    Retourne True si le match doit encore être affiché.
    Filtre les matchs dont le coup d'envoi date de plus de 5 minutes.
    """
    if not match or not match.kickoff_at:
        return False
    ko = match.kickoff_at
    # Sécurité : normalise en UTC si le datetime est naïf
    if ko.tzinfo is None:
        ko = ko.replace(tzinfo=timezone.utc)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=MATCH_GRACE_MINUTES)
    return ko >= cutoff
