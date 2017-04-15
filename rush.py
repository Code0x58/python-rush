# -*- encoding: utf-8 -*-
"""
Provide a class for orchestrating the rush of some yielding callable.
"""
from __future__ import absolute_import

import sys
from collections import defaultdict
from datetime import timedelta
from threading import Condition, Event, Thread
from time import time

__all__ = ['Rusher', 'rush', 'rush_and_report']


class Rusher(object):
    """
    A class for orchestrating the rush of some yielding callable.

    This class creates self.thread_count worker threads which will be used to
    rush a resource when they are ready.

    During Rusher.rush() the workers are created and run until they yield.
    Once all the workers have yielded they are then woken up at once so they
    can rush.
    """
    def __init__(self, worker, thread_count=2):
        self.worker = worker
        self.thread_count = thread_count
        # the orchestrator waits for notification of this from the workers
        self.ready_progress = Condition()
        self._total_ready = 0
        # this triggers the rush in the worker threads
        self.trigger = Event()
        self._return_list = []
        self._threads = []

    def _create_threads(self):
        """
        Create and start the worker threads so they can get ready to rush.
        """
        self._wait_for_threads()
        self._threads = []
        self._return_list = []
        for i in range(self.thread_count):
            thread = Thread(target=self._work, args=(i,))
            thread.start()
            self._threads.append(thread)

    def _wait_for_threads(self, end_time=None):
        """
        Wait for all worker threads to finish.

        Unfinished threads are not killed.
        """
        for thread in self._threads:
            if end_time is not None:
                max_wait = end_time - time()
                if max_wait < 0:
                    return
            else:
                max_wait = None
            thread.join(max_wait)
            # this is very likely to happen if the timeout tripped
            if thread.is_alive():
                return

        # all workers returned before end_time
        return

    def rush(self, max_seconds=None):
        """
        Create worker threads and trigger their rush once they are ready.

        max_seconds is either None for no limiting, or a float.

        Returns (duration, results).
        """
        with self.ready_progress:
            self._total_ready = 0
            self._create_threads()
            self.ready_progress.wait()

        start = time()
        wait_until = time() + max_seconds if max_seconds else None

        self.trigger.set()
        self._wait_for_threads(wait_until)
        self.trigger.clear()

        results = tuple(self._return_list)
        end = time()
        duration = end-start
        return duration, results

    def _work(self, index):
        """
        Interface with the orchestration in the rush method, to run the worker.

        self.worker is iterated once so it can preform any needed prepairation,
        then again when this worker thread is awakened in self.rush() when
        the final worker notifies it that it has completed.

        Each worker is passed a unique index 0 ≤ index < self.thread_count.

        The result of the second yield to self._return_list.
        """
        worker_run = iter(self.worker(index, self.thread_count))
        next(worker_run)
        with self.ready_progress:
            self._total_ready += 1
            if self._total_ready == self.thread_count:
                self.ready_progress.notify_all()
        # Wait for the trigger to be fired
        self.trigger.wait()
        try:
            result = next(worker_run)
        except StopIteration:
            result = None
        self._return_list.append(result)

    def rush_and_report(self, max_seconds=None, output=sys.stdout):
        """
        Perform a rush and wite a summary of results to an output.

        This requires the results of self.work be hashable.

        Returns (duration, results) from the rush method.
        """
        duration, results = self.rush(max_seconds)
        # This avoids the use of collections.Counter to be 2.6+ compatible
        counts = defaultdict(int)
        for result in results:
            counts[result] += 1
        output.write("{} threads completed in {}, results:\n".format(
            len(results),
            str(timedelta(seconds=duration)).lstrip('0:'),
        ))
        for result, count in counts.items():
            output.write("\t{}: {}\n".format(result, count))

        return (duration, results)


def rush(worker, thread_count=2, max_seconds=None):
    """
    Convenience function for Rusher.rush
    """
    return (Rusher(worker, thread_count)
            .rush(max_seconds=max_seconds))


def rush_and_report(worker, thread_count=2, max_seconds=None, output=sys.stdout):
    """
    Convenience function for Rusher.rush_and_report
    """
    return (Rusher(worker, thread_count)
            .rush_and_report(max_seconds=max_seconds, output=output))
