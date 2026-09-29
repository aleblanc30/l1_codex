from collections import OrderedDict
from threading import RLock

from codex import logger

# Caches keyed on a database object (for example results computed for one neuron set). They hold on to
# a view after the view cache dropped it, so they are cleared when a view is evicted.
_SHARED_CACHE_CLEARERS = []


def cleared_when_a_view_is_evicted(cached_function):
    """Decorator for a functools.lru_cache function whose arguments include a database."""
    _SHARED_CACHE_CLEARERS.append(cached_function.cache_clear)
    return cached_function


def clear_shared_caches():
    for clear in _SHARED_CACHE_CLEARERS:
        clear()


class ViewCache(object):
    """Keeps the databases built for neuron sets within a budget of cells, dropping the least recently
    used first. Memory use follows the number of cells a view holds (about 30 MB per 1,000), so the
    budget is counted in cells. Pinned keys are never dropped and do not count towards the budget, and
    the view just asked for is always kept, even if it alone is over the budget.
    A budget of 0 means no limit."""

    def __init__(self, max_cells, pinned=(), on_evict=None):
        self.max_cells = max_cells
        self.pinned = set(pinned)
        self.on_evict = on_evict
        self._entries = OrderedDict()  # key -> (view, cells)
        self._lock = RLock()

    def keys(self):
        with self._lock:
            return list(self._entries)

    @property
    def cells(self):
        with self._lock:
            return sum(c for k, (_, c) in self._entries.items() if k not in self.pinned)

    def get(self, key, cells, build):
        with self._lock:
            if key in self._entries:
                self._entries.move_to_end(key)
                return self._entries[key][0]
            view = build()
            self._entries[key] = (view, cells)
            self._evict(keep=key)
            return view

    def _evict(self, keep):
        if not self.max_cells:
            return
        evicted = []
        for key in list(self._entries):
            if self.cells <= self.max_cells:
                break
            if key == keep or key in self.pinned:
                continue
            view, _ = self._entries.pop(key)
            evicted.append((key, view))
        if evicted:
            logger.info(
                f"Dropped the views of neuron sets {[k for k, _ in evicted]} to stay within "
                f"{self.max_cells} cells"
            )
            clear_shared_caches()
            for key, view in evicted:
                if self.on_evict:
                    self.on_evict(key, view)
