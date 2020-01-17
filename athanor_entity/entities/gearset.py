from django.conf import settings

from evennia.utils.utils import class_from_module

from athanor.utils.mixins import HasLocks


class GearSlot(object):

    def __init__(self, gearset, name):
        self.gearset = gearset
        self.name = name
        self.layers = dict()
        self.contents = set()

    def available_layer(self, layer=None):
        """
        Decides whether there's a layer available for this Slot and announces what it is, if any.

        In the default implementation, there are always more layers available. This probably isn't
        what you want.

        Args:
            layer (int or None): if it's an int, this will instead check for if a SPECIFIC LAYER is
                available.

        Returns:
            layer (int or None): This can be 0, so be sure to check for None and not just False.
        """
        if layer is not None:
            return layer if layer not in self.layers else None
        if not self.contents:
            return 0
        return max(self.layers.keys()) + 1


class GearSet(HasLocks):
    """
    This is a basic gearset. Although it's usable all on its own, it's meant to be sub-classed from.
    """
    lockstring = "see:self();view:self();equip:self();unequip:self()"

    def __init__(self, handler, name, in_data=None):
        self.persistent = handler.owner.persistent
        self.name = name
        self.handler = handler
        if in_data is None:
            if self.persistent:
                in_data = self.handler.owner.attributes.get(key=name, category='gear', default=dict())
            else:
                in_data = dict()
        self.data = in_data
        self.contents = set()
        self.gearslots = dict()
        self.weight = 0
        self.db_lock_storage = self.lockstring

    def __str__(self):
        return self.name

    def get_gearslot(self, slot_name):
        if (found := self.gearslots.get(slot_name, None)):
            return found
        slot_class = class_from_module(settings.SPECIAL_GEARSLOT_CLASSES.get(slot_name, settings.BASE_GEARSLOT_CLASS))
        new_slot = slot_class(self, slot_name)
        self.gearslots[slot_name] = new_slot
        return new_slot

    def at_before_equip(self, entity):
        pass

    def equip(self, entity, slot_name=None, slot_layer=None):
        if entity in self.contents:
            raise ValueError(f"{entity} is already in {self.handler.owner}'s {self} inventory!")
        self.at_before_equip(entity)
        self.contents.add(entity)
        entity.inventory_location = self
        self.at_after_equip(entity)

    def at_after_equip(self, entity):
        pass

    def at_before_unequip(self, entity):
        pass

    def unequip(self, entity):
        if entity not in self.contents:
            raise ValueError(f"{entity} is not in {self.handler.owner}'s {self} inventory!")
        self.at_before_unequip(entity)
        self.contents.remove(entity)
        entity.inventory_location = None
        self.at_after_unequip(entity)

    def at_after_unequip(self, entity):
        pass

    def clear(self, slot_name=None):
        pass

    def all(self):
        return list(self.contents)
