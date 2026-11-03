"""Check the public pose template without creating a private poses.py file."""
import importlib.util
import pathlib
import unittest


class PoseMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).resolve().parents[1] / 'poses.example.py'
        spec = importlib.util.spec_from_file_location('pose_example', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.classify = staticmethod(module.classify)
        cls.POSES = module.POSES

    def test_all_six_targets_exist_but_not_configured(self):
        self.assertEqual(set(self.POSES), {'FIST', '1 finger', '2 fingers', '3 fingers', '4 fingers', '5 fingers'})
        self.assertTrue(all(item[0] is None for item in self.POSES.values()))

    def test_expected_mapping(self):
        states = [
            ((0, 0, 0, 0, 0), 'FIST'),
            ((0, 1, 0, 0, 0), '1 finger'),
            ((0, 1, 1, 0, 0), '2 fingers'),
            ((0, 1, 1, 1, 0), '3 fingers'),
            ((0, 1, 1, 1, 1), '4 fingers'),
            ((1, 1, 1, 1, 1), '5 fingers'),
        ]
        for state, expected in states:
            with self.subTest(state=state):
                self.assertEqual(self.classify(state), expected)


if __name__ == '__main__':
    unittest.main()
