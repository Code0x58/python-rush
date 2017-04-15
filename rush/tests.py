# -*- encoding: utf-8 -*-
"""
Use unittest to ensure certain functionailty.
"""
from __future__ import absolute_import
import unittest
from time import sleep

from rush import Rusher


class TestRusher(unittest.TestCase):
    """
    Test the Rusher superclass.
    """
    @staticmethod
    def _sleepy_worker(index, _):
        """
        Sleep for secounds * index
        """
        sleep_time = index
        yield
        sleep(sleep_time)
        yield index

    def test_worker_steps(self):
        """
        Check that there are only two steps for a worker.
        """
        target_thread_count = 3

        class StepCounter(object):
            """
            Count the number of times a step is taken in the worker.
            """
            def __init__(self):
                self.a_steps = 0
                self.b_steps = 0
                self.c_steps = 0

            def __call__(self, index, thread_count):
                self.a_steps += 1
                yield
                self.b_steps += 1
                yield
                self.c_steps += 1

        step_counter = StepCounter()

        rusher = Rusher(step_counter, target_thread_count)
        rusher.rush()
        self.assertEqual(step_counter.a_steps, target_thread_count)
        self.assertEqual(step_counter.b_steps, target_thread_count)
        self.assertEqual(step_counter.c_steps, 0)

    def test_rush(self):
        """
        Check that a rush without a timeout works as expected.
        """
        rusher = Rusher(self._sleepy_worker, 1)
        # test with only one worker thread
        _, results = rusher.rush()
        self.assertEqual(sorted(results), [0])
        # test with two worker threads
        rusher.thread_count = 2
        _, results = rusher.rush()
        self.assertEqual(sorted(results), [0, 1])

    def test_max_seconds(self):
        """
        Check that a rush with timeout works as expected.
        """
        rusher = Rusher(self._sleepy_worker, 2)
        # check that the first worker returns
        _, results = rusher.rush(0.5)
        self.assertEqual(sorted(results), [0])
        # check both workers return
        _, results = rusher.rush(1.5)
        self.assertEqual(sorted(results), [0, 1])


if __name__ == '__main__':
    unittest.main()
