from inspect import getmembers, isfunction
import spidertools.storage.data.filtering as filtering
import spidertools.storage.data.sorting as sorting

def _selector(filter_type, module):
    # Get all filter functions
    results = getmembers(module, isfunction)

    # Return the actual function connected to the filter type.
    for t, f in results:
        if filter_type == t:
            return f

    return None

def filter_selector(filter_type):
    return _selector(filter_type, filtering)


def sort_selector(sort_type):
    return _selector(sort_type, sorting)
