# Rush
This python module is for making simple tools that rush a resource, such as an
API endpoint or web UI. This runs with both Python 2.6+ or 3.0+.

This was originally created to test the throttling of authentication attempts.
It is quite basic, but was enough to get good results from a Django based web
app. I imagine that this is good enough to indicate if rate limiting is
reasonably implemented on faster systems (more likely to come down to network?).

## Example
This example attempts to connect to an API endpoint which will throttle after
10 requests:

```python
try:
    # Python 2
    from xmlrpclib import ServerProxy, Fault
except ImportError:
    # Python 3
    from xmlrpc.client import ServerProxy, Fault
from rush import Rusher


def api_auth_tester(index, thread_count):
    """
    Rush the API with invalid authentication attempts.
    """
    # prepare the worker
    proxy = ServerProxy('https://badname:supersecretpassword@api.memset.com/v1/xmlrpc/')
    yield  # yield to indicate that the worker is ready to rush
    # rush
    try:
        proxy.server.list()
    except Fault as error:
        # yield a string indicating the result
        if error.faultCode == 4:  # bad username/pass
            yield 'attempted'
        elif error.faultCode == 12:  # throttled
            yield 'throttled'

print("API rate limiting test:")
# the API will throttle after 10 requests, so make 9 requests first, then rush two calls
rusher = Rusher(api_auth_tester, 9)
# preform the first 9 requests so the next request should set a throttling indicator
duration, results = rusher.analyse()
# change the number of threads we want to make
rusher.thread_count = 2
# only one call should not be throttled
rusher.analyse()
```
This will produce output like the following:
```
API rate limiting test:
9 threads completed in .747115, results:
	attempted: 9
2 threads completed in .127208, results:
	attempted: 1
	throttled: 1
```
