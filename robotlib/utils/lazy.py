class lazy_property:
    def __init__(self, func):
        self.func = func
        self.attr_name = '_lazy_' + func.__name__

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if not hasattr(instance, self.attr_name):
            setattr(instance, self.attr_name, self.func(instance))
        return getattr(instance, self.attr_name)