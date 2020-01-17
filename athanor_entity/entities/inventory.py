from collections import defaultdict

from athanor.utils.mixins import HasLocks


class Inventory(HasLocks):
    """
    This is a basic inventory. Although it's usable all on its own, it's meant to be sub-classed from.
    """
    lockstring = "see:self();view:self();get:self();put:self()"

    def __init__(self, handler, name, in_data=None):
        self.persistent = handler.owner.persistent
        self.name = name
        self.handler = handler
        if in_data is None:
            if self.persistent:
                in_data = self.handler.owner.attributes.get(key=name, category='inventory', default=dict())
            else:
                in_data = dict()
        self.data = in_data
        self.contents = set()
        self.equipped = set()
        self.slots = defaultdict(dict)
        self.prototype_index = defaultdict(set)
        self.weight = 0
        self.db_lock_storage = self.lockstring

    def __str__(self):
        return self.name

    def at_before_add(self, entity):
        pass

    def add(self, entity, sort_index=None):
        if entity in self.contents:
            raise ValueError(f"{entity} is already in {self.handler.owner}'s {self} inventory!")
        self.at_before_add(entity)
        self.contents.add(entity)
        entity.inventory_location = self
        self.at_after_add(entity)

    def at_after_add(self, entity):
        pass

    def at_before_remove(self, entity):
        pass

    def remove(self, entity):
        if entity not in self.contents:
            raise ValueError(f"{entity} is not in {self.handler.owner}'s {self} inventory!")
        self.at_before_remove(entity)
        self.contents.remove(entity)
        entity.inventory_location = None
        self.at_after_remove(entity)

    def at_after_remove(self, entity):
        pass

    def all(self):
        return list(self.contents)
