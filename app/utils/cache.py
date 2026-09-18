"""
Cache mémoire simple pour endpoints FastAPI.

Supporte les routes synchrones ET asynchrones :
- Route `def`   → cache synchrone (reste dans le thread pool)
- Route `async` → cache asynchrone (reste dans l'event loop)
"""
import inspect
from datetime import datetime, timedelta
from functools import wraps

_caches: dict = {}


def cache_memory(ttl_seconds: int = 300, key: str = None):
    """
    Cache mémoire en RAM pour les endpoints GET.
    
    - ttl_seconds : durée de vie en secondes
    - key : nom du cache (par défaut = nom de la fonction)
    """
    def decorator(func):
        cache_key = key or func.__name__
        is_async = inspect.iscoroutinefunction(func)

        def _get_cached():
            """Retourne (donnée, valide)."""
            if cache_key not in _caches:
                return None, False
            entry = _caches[cache_key]
            age = (datetime.now() - entry["time"]).total_seconds()
            if age < ttl_seconds:
                print(f"⚡ [{cache_key}] cache HIT (age={age:.0f}s)")
                return entry["data"], True
            return None, False

        def _set_cache(result):
            _caches[cache_key] = {"data": result, "time": datetime.now()}

        if is_async:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                cached, valid = _get_cached()
                if valid:
                    return cached

                print(f"🔄 [{cache_key}] cache MISS — calcul en cours...")
                start = datetime.now()
                result = await func(*args, **kwargs)
                elapsed = (datetime.now() - start).total_seconds()
                print(f"✅ [{cache_key}] calcul terminé en {elapsed:.2f}s")

                _set_cache(result)
                return result

            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                cached, valid = _get_cached()
                if valid:
                    return cached

                print(f"🔄 [{cache_key}] cache MISS — calcul en cours...")
                start = datetime.now()
                result = func(*args, **kwargs)
                elapsed = (datetime.now() - start).total_seconds()
                print(f"✅ [{cache_key}] calcul terminé en {elapsed:.2f}s")

                _set_cache(result)
                return result

            return sync_wrapper

    return decorator


def invalidate_cache(key: str = None):
    """Invalide un cache (ou tous si key=None)."""
    if key:
        _caches.pop(key, None)
    else:
        _caches.clear()


def cache_info():
    """Retourne l'état actuel du cache (debug)."""
    now = datetime.now()
    return {
        k: {
            "age_seconds": round((now - v["time"]).total_seconds(), 1),
            "cached_at": v["time"].isoformat(),
        }
        for k, v in _caches.items()
  }
