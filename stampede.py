#!/usr/bin/env python
from collections import Counter
from datetime import timedelta
from threading import Thread, Event, active_count
from time import time, sleep
from xmlrpclib import ServerProxy, Fault


class Stampede(object):
    """
    This class creates self.thread_count threads, the task of these threads is
    self.work which should wait for trigger.set
    """
    def __init__(self, thread_count):
        self.thread_count = thread_count
        self.trigger = Event()
        self.return_list = []
        self.threads = []
        self.ready = []

    def _create_threads(self):
        """
        Create and start the worker threads so they can get ready to rush.
        """
        self._wait_for_threads()
        self.threads = []
        self.return_list = []
        self.ready = []
        for _ in range(self.thread_count):
            thread = Thread(target=self.work)
            thread.start()
            self.threads.append(thread)

    def _wait_for_threads(self):
        """
        Wait for any worker threads to finish.
        """
        for thread in self.threads:
            thread.join()

    def rush(self, max_time):
        """
        Start up all the worker threads, wait for them to be ready to rush
        and then start the rush event. Returns the duration and results.
        """
        self._create_threads()
        while len(self.ready) != self.thread_count:
            sleep(.05)
        start = time()
        self.trigger.set()
        if max_time > 0:
            # this is so the workers have roughly max_time to rush
            sleep(float(max_time)-0.004)
        else:
            while active_count() != 1:
                sleep(.05)
        results = tuple(self.return_list)
        end = time()
        duration = end-start
        return duration, results

    def work(self):
        """
        This should be overridden in a subclass and called as soon as the
        worker thread is ready to begin rushing it's main task.
        """
        self.ready.append(1)
        self.trigger.wait()

    def work_return(self, result):
        """
        This returns a worker thread result by appending it to the result
        list - lists are thread safe.
        """
        self.return_list.append(result)

    def analyse(self, max_time=0):
        """
        Print the number of completed workers, duration and result counts.
        """
        duration, results = self.rush(max_time)
        counts = Counter(results)
        print "%s threads completed in %s, results:\n\t%s" % (
                len(results),
                str(timedelta(seconds=duration)).lstrip('0:'),
                "\n\t".join("%s: %s" % result for result in counts.items()),
        )


class UserAPIFakeAuthTester(Stampede):
    """
    Rush the API with username+password authentication attempts (fake account).
    """
    uri = 'https://badname:supersecretpassword@api.memset.com/v1/xmlrpc/'

    def work(self):
        proxy = ServerProxy(self.uri)
        super(UserAPIFakeAuthTester, self).work()
        try:
            proxy.server.list()
        except Fault as error:
            if error.faultCode == 4:  # bad username/pass
                return self.work_return('attempted')
            elif error.faultCode == 12:  # throttled
                return self.work_return('throttled')


if __name__ == '__main__':
    print
    print "API user+password (fake account) authentication test:"
    UserAPIFakeAuthTester(5).analyse()

