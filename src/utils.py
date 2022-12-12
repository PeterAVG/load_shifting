from functools import wraps
from time import time
from typing import Any, Callable


def timing(print_output: bool = False) -> Callable:
    def timing_decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrap(*args: Any, **kw: Any) -> Any:
            ts = time()
            result = f(*args, **kw)
            te = time()
            text = "func:%r took: %2.4f sec" % (f.__name__, te - ts)
            text += f" | Result: {result})" if print_output else ""
            print(text)
            return result

        return wrap

    return timing_decorator
