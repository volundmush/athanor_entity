from evennia.utils.utils import lazy_property
from athanor_entity.entities.handlers import ItemHandler


class HasInventory(object):

    @lazy_property
    def items(self):
        return ItemHandler(self)
