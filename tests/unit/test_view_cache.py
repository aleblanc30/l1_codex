import gc
import weakref
from functools import lru_cache
from threading import Thread
from unittest import TestCase

from codex.data.instance_cache import instance_cache
from codex.data.neuron_data_initializer import initialize_neuron_data
from codex.data.view_cache import ViewCache, cleared_when_a_view_is_evicted
from tests.l1_fixture import initialize_kwargs


class Thing:
    def __init__(self, name):
        self.name = name


def make_cache(max_cells, pinned=(), on_evict=None):
    built = []

    def get(key, size):
        def build():
            built.append(key)
            return Thing(key)

        return cache.get(key, size, build)

    cache = ViewCache(max_cells=max_cells, pinned=pinned, on_evict=on_evict)
    return cache, get, built


class ViewCacheTest(TestCase):
    def test_a_view_is_built_once(self):
        cache, get, built = make_cache(100)
        first = get("a", 10)
        self.assertIs(first, get("a", 10))
        self.assertEqual(["a"], built)

    def test_the_oldest_view_goes_first_when_the_budget_is_exceeded(self):
        cache, get, _ = make_cache(100)
        get("a", 60)
        get("b", 30)
        get("c", 40)
        self.assertEqual(["b", "c"], cache.keys())
        self.assertEqual(70, cache.cells)

    def test_a_view_that_was_used_again_stays(self):
        cache, get, _ = make_cache(100)
        get("a", 40)
        get("b", 40)
        get("a", 40)
        get("c", 40)
        self.assertEqual(["a", "c"], cache.keys())

    def test_several_views_are_dropped_if_needed(self):
        cache, get, _ = make_cache(100)
        get("a", 30)
        get("b", 30)
        get("c", 30)
        get("d", 90)
        self.assertEqual(["d"], cache.keys())

    def test_pinned_views_are_never_dropped_and_do_not_count(self):
        cache, get, _ = make_cache(100, pinned=["default"])
        get("default", 500)
        get("a", 60)
        get("b", 60)
        self.assertEqual(["default", "b"], cache.keys())
        self.assertEqual(60, cache.cells)

    def test_the_newest_view_is_kept_even_if_it_alone_exceeds_the_budget(self):
        cache, get, _ = make_cache(100)
        get("a", 50)
        get("huge", 300)
        self.assertEqual(["huge"], cache.keys())

    def test_a_dropped_view_is_built_again_when_asked_for(self):
        cache, get, built = make_cache(50)
        get("a", 40)
        get("b", 40)
        get("a", 40)
        self.assertEqual(["a", "b", "a"], built)

    def test_evictions_are_reported(self):
        gone = []
        cache, get, _ = make_cache(50, on_evict=lambda key, view: gone.append(key))
        get("a", 40)
        get("b", 40)
        self.assertEqual(["a"], gone)

    def test_no_budget_means_no_dropping(self):
        cache, get, _ = make_cache(0)
        for i in range(20):
            get(f"v{i}", 10**6)
        self.assertEqual(20, len(cache.keys()))

    def test_concurrent_requests_build_a_view_once(self):
        built = []
        cache = ViewCache(max_cells=1000)

        def build():
            built.append(1)
            return Thing("a")

        results = []
        threads = [
            Thread(target=lambda: results.append(cache.get("a", 10, build)))
            for _ in range(8)
        ]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(1, len(built))
        self.assertEqual(1, len({id(r) for r in results}))


class EvictionClearsSharedCachesTest(TestCase):
    def test_registered_caches_are_cleared_when_a_view_is_evicted(self):
        calls = []

        @cleared_when_a_view_is_evicted
        @lru_cache
        def expensive(x):
            calls.append(x)
            return x

        expensive(1)
        expensive(1)
        self.assertEqual([1], calls)
        cache, get, _ = make_cache(50)
        get("a", 40)
        get("b", 40)
        expensive(1)
        self.assertEqual([1, 1], calls)


class InstanceCacheTest(TestCase):
    def test_results_are_cached_per_instance(self):
        class Counter:
            def __init__(self):
                self.calls = 0

            @instance_cache
            def double(self, x, plus=0):
                self.calls += 1
                return 2 * x + plus

        a, b = Counter(), Counter()
        self.assertEqual(4, a.double(2))
        self.assertEqual(4, a.double(2))
        self.assertEqual(5, a.double(2, plus=1))
        self.assertEqual(1 + 1, a.calls)
        self.assertEqual(4, b.double(2))
        self.assertEqual(1, b.calls)

    def test_an_instance_can_be_freed(self):
        class Holder:
            @instance_cache
            def value(self):
                return [1, 2, 3]

        holder = Holder()
        holder.value()
        ref = weakref.ref(holder)
        del holder
        gc.collect()
        self.assertIsNone(ref())

    def test_the_cache_is_bounded(self):
        class Counter:
            calls = 0

            @instance_cache
            def ident(self, x):
                Counter.calls += 1
                return x

        c = Counter()
        for i in range(500):
            c.ident(i)
        c.ident(0)  # long gone from the cache
        self.assertEqual(501, Counter.calls)


class NeuronDBViewsTest(TestCase):
    """Fixture sets: winding (2 cells, the default), soma (1), and one paper set (1)."""

    def setUp(self):
        self.db = initialize_neuron_data(**initialize_kwargs())

    def test_the_default_view_stays_while_others_come_and_go(self):
        self.db.view_cache.max_cells = 1
        default = self.db.view("winding")
        self.db.view("soma")
        self.db.view("paper-zwart-et-al-2016")
        self.assertIs(default, self.db.view("winding"))
        self.assertEqual(
            ["paper-zwart-et-al-2016", "winding"], sorted(self.db.view_cache.keys())
        )

    def test_an_evicted_view_can_be_freed(self):
        self.db.view_cache.max_cells = 1
        soma = self.db.view("soma")
        soma.search("")  # fills the view's own caches
        soma.input_sets()
        ref = weakref.ref(soma)
        del soma
        self.db.view("paper-zwart-et-al-2016")
        gc.collect()
        self.assertIsNone(ref())

    def test_an_evicted_view_is_rebuilt_on_demand(self):
        self.db.view_cache.max_cells = 1
        first = self.db.view("soma")
        self.db.view("paper-zwart-et-al-2016")
        again = self.db.view("soma")
        self.assertIsNot(first, again)
        self.assertEqual(set(first.search("")), set(again.search("")))

    def test_the_budget_comes_from_the_configuration(self):
        from codex.configuration import NEURON_SET_VIEW_CELL_BUDGET

        self.assertEqual(NEURON_SET_VIEW_CELL_BUDGET, self.db.view_cache.max_cells)
