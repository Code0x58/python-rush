#!/usr/bin/env python
from collections import defaultdict
from datetime import timedelta
from threading import Thread, Event, Condition
from time import time


class Rusher(object):
    """
    This class is intended to create self.thread_count worker threads which
    will be used to rush a resource. This can be used to test rate limiting.

    During Rusher.rush() the workers are created and run until they yield.
    Once all the workers have yielded they are then run at once so they can
    rush a resource.
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
        Wait for all worker threads to finish. Return True if all finished
        before the specified end time.

        Unfinished threads are not killed.
        """
        for thread in self.threads:
            if end_time is not None:
                max_wait = end_time - time()
                if max_wait < 0:
                    return False
            else:
                max_wait = None
            thread.join(max_wait)
            # this is likely to happen if the timeout happened
            if thread.is_alive():
                return False
        return True

    def rush(self, max_seconds=None):
        """
        Start up all the worker threads, wait for them to be ready to rush
        and then fire the rush event.

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
        Iterates the work generator once for it to prepare itself, then a
        second time when all the workers are ready to rush.

        Appends the result of the second yield to self.return_list
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

    def work(self):
        """
        Override this method to do work and return a result.
        """
        # preform any setup here
        yield  # indicate that the worker has set itself up
        # do work work here
        yield "Finished"  # return result of work here

    def analyse(self, max_seconds=None):
        """
        Perform a rush and print the numer of completed workers, duration,
        and result counts. This requires results to be hashable.

        Returns (duration, results) from the rush method.
        """
        duration, results = self.rush(max_seconds)
        # This avoids the use of collections.Counter to be 2.6+ compatible
        counts = defaultdict(int)
        for result in results:
            counts[result] += 1
        print("{} threads completed in {}, results:".format(
            len(results),
            str(timedelta(seconds=duration)).lstrip('0:'),
        ))
        for result, count in counts.items():
            print("\t{}: {}".format(result, count))

        return (duration, results)


if __name__ == '__main__':
    try:
        from xmlrpclib import ServerProxy, Fault
    except ImportError:
        from xmlrpc.client import ServerProxy, Fault

    class UserAPIInvalidAuthTester(Rusher):
        """
        Rush the API with invalid authentication attempts.
        """
        uri = 'https://badname:supersecretpassword@api.memset.com/v1/xmlrpc/'

        def work(self):
            proxy = ServerProxy(self.uri)
            yield
            try:
                proxy.server.list()
            except Fault as error:
                if error.faultCode == 4:  # bad username/pass
                    yield 'attempted'
                elif error.faultCode == 12:  # throttled
                    yield 'throttled'

    print("API rate limiting test:")
    # the API will throttle after 10 requests
    rusher = UserAPIInvalidAuthTester(9)
    # preform 9 requests so the next request should set a throttling indicator
    duration, results = rusher.analyse()
    # change the number of threads we want to make
    rusher.thread_count = 2
    # only one call should not be throttled
    rusher.analyse()
