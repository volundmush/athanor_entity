class Body(object):

    @property
    def persistent(self):
        return self.handler.persistent

    def __init__(self, handler, name, data=None):
        self.handler = handler
        self.name = name
        self.slots = dict()
