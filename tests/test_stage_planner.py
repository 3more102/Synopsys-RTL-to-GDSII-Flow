import importlib.util
from pathlib import Path
import unittest

MOD = Path(__file__).resolve().parents[1] / 'python' / 'plan_rebuild.py'
spec = importlib.util.spec_from_file_location('plan_rebuild', MOD)
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)

class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.g={'a':{'depends_on':[]},'b':{'depends_on':['a']},'c':{'depends_on':['b']},'side':{'depends_on':['a']}}
    def test_topological_order(self):
        order=plan.topo(self.g)
        self.assertLess(order.index('a'),order.index('b'))
        self.assertLess(order.index('b'),order.index('c'))
    def test_descendants(self):
        self.assertEqual(plan.descendants(self.g,{'b'}),{'b','c'})
    def test_ancestors(self):
        self.assertEqual(plan.ancestors(self.g,'c'),{'a','b','c'})
    def test_cycle_detection(self):
        with self.assertRaises(ValueError):
            plan.topo({'a':{'depends_on':['b']},'b':{'depends_on':['a']}})

if __name__=='__main__':
    unittest.main()
