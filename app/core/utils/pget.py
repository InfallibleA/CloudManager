import functools


def pget(obj, path, default=None, post_processing=None):
    if issubclass(type(obj), dict):
        res = getterdict(obj, path, default)
    else:
        res = rgetattr(obj, path, default)

    if res != default and callable(post_processing):
        return post_processing(res)
    else:
        return res


def getterdict(dictionary, keys, default=None):
    return functools.reduce(
        lambda d, key: (d.get(key, None) or default) if isinstance(d, dict) else default,
        keys.split('.'),
        dictionary,
    )


def rgetattr(obj, attr, *args):
    """
    Modifies normal getattr function to work with nested properties
    for example: rgetattr(obj, "x.y.z","-") will return "-" as default value
    if x doesn't have y property or y doesn't have z property.
    If some property in chain dosn't exist and default value is not provided to function call
    AttributeError exception will be raised.
    """

    def _getattr(obj, attr):
        return getattr(obj, attr, *args)

    return functools.reduce(_getattr, [obj] + attr.split('.'))
