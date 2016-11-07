# -*- encoding: utf-8 -*-
"""
Provide a superclass for rushing a resource.
"""
from __future__ import absolute_import
import sys
from collections import defaultdict
from datetime import timedelta
from threading import Thread, Event, Condition
from time import time


class Rusher(object):
    """
    Provide a simple interface for making rushing resource.

    This class creates self.thread_count worker threads which will be used to
    rush a resource when they are ready.

    During Rusher.rush() the workers are created and run until they yield.
    Once all the workers have yielded they are then woken up at once so they
    can rush a resource.
    """
    def __init__(self, thread_count):
        self.thread_count = thread_count
        # the orchestrator waits for notification of this from the workers
        self.ready_progress = Condition()
        self._total_ready = 0
        # this triggers the rush in the worker threads
        self.trigger = Event()
        self.return_list = []
        self.threads = []
        # this can be used in worker threads to see if they should give up
        self.rushing = False

    def _create_threads(self):
        """
        Create and start the worker threads so they can get ready to rush.
        """
        self._wait_for_threads()
        self.threads = []
        self.return_list = []
        for _ in range(self.thread_count):
            thread = Thread(target=self._work)
            thread.start()
            self.threads.append(thread)

    def _wait_for_threads(self, end_time=None):
        """
        Wait for all worker threads to finish.

        Unfinished threads are not killed.
        """
        for thread in self.threads:
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
        self.ready_progress.acquire()
        self._total_ready = 0
        self._create_threads()
        self.ready_progress.wait()
        self.ready_progress.release()

        start = time()
        wait_until = time() + max_seconds if max_seconds else None

        self.rushing = True
        self.trigger.set()
        self._wait_for_threads(wait_until)
        self.trigger.clear()
        self.rushing = False

        results = tuple(self.return_list)
        end = time()
        duration = end-start
        return duration, results

    def _work(self):
        """
        Interface with the orchestration in the rush method, to run the worker.

        self.work is iterated once so it can preform any needed prepairation,
        then again when this worker thread is awakened in self.rush() when
        the final worker notifies it that it has completed.

        The result of the second yield to self.return_list.
        """
        worker = iter(self.work())
        next(worker)
        self.ready_progress.acquire()
        self._total_ready += 1
        if self._total_ready == self.thread_count:
            self.ready_progress.notify_all()
        self.ready_progress.release()
        # Wait for the trigger to be fired
        self.trigger.wait()
        try:
            result = next(worker)
        except StopIteration:
            result = None
        self.return_list.append(result)

    @staticmethod
    def work():
        """
        Override this method to do work and return a result.
        """
        # preform any setup here
        yield  # indicate that the worker has set itself up
        # do work work here
        yield "Finished"  # return result of work here

    def analyse(self, max_seconds=None, output=sys.stdout):
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
