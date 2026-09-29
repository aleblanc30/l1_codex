from collections import OrderedDict
from functools import wraps
from threading import Lock

DEFAULT_MAX_ENTRIES = 128


def instance_cache(method, max_entries=DEFAULT_MAX_ENTRIES):
    """Caches a method's results on the instance, most recently used entries first to stay.

    Unlike functools.lru_cache on a method, the cache is not held by the class, so it does not keep the
    instance alive: dropping the instance frees its cached results."""
    name = method.__qualname__
    lock = Lock()

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        with lock:
            cache = self.__dict__.setdefault("_instance_caches", {}).setdefault(
                name, OrderedDict()
            )
            if key in cache:
                cache.move_to_end(key)
                return cache[key]
        result = method(self, *args, **kwargs)
        with lock:
            cache[key] = result
            cache.move_to_end(key)
            while len(cache) > max_entries:
                cache.popitem(last=False)
        return result

    return wrapper
