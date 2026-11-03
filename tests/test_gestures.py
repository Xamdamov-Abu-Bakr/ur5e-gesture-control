"""Pure-Python smoke tests; these do not connect to a robot or a camera."""
import unittest
from gestures import GestureHold


class GestureHoldTests(unittest.TestCase):
    def test_three_second_confirmation(self):
        hold = GestureHold()
        for i in range(6):
            _, _, _, ready = hold.push(i * 0.5, "3 fingers")
            self.assertFalse(ready)
        leader, ratio, progress, ready = hold.push(3.0, "3 fingers")
        self.assertEqual(leader, "3 fingers")
        self.assertEqual(ratio, 1.0)
        self.assertEqual(progress, 1.0)
        self.assertTrue(ready)

    def test_single_frame_does_not_trigger(self):
        hold = GestureHold()
        self.assertFalse(hold.push(0.0, "FIST")[3])


if __name__ == "__main__":
    unittest.main()
