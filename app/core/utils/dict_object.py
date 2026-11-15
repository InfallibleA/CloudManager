class DictObject:
    def __init__(self, in_dict):
        for k, v in in_dict.items():
            if isinstance(v, (list, tuple)):
                setattr(self, k, [DictObject(x) if isinstance(x, dict) else x for x in v])
            else:
                setattr(self, k, DictObject(v) if isinstance(v, dict) else v)


def make_object(**kwargs):
    return DictObject(kwargs)
