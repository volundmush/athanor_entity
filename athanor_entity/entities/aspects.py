"""
The Aspect system is SUPPOSED to handle things like Character Classes, Final Fantasy Jobs, Professions, etc.
Also Species/Races.

We'll see how well that works out.
"""


class Aspect(object):
    name = "Unknown Aspect"

    def __init__(self, handler, slot, in_data=None):
        self.persistent = handler.owner.persistent
        self.handler = handler
        self.slot = slot
        if in_data is None:
            if self.persistent:
                in_data = self.handler.owner.attributes.get(key=slot, category='aspect', default=dict())
            else:
                in_data = dict()
        self.data = in_data

    def __str__(self):
        return self.name

    def at_before_equip(self, entity, gearset, slot):
        """
        This is called whenever the owner wants to equip an item.
        If it returns false, the item will not be equipped.
        Override this hook to implement Aspect-specified rules about
        who can equip what.

        Args:
            entity (Entity): The item being equipped.
            gearset (gearset): The gearset being equipped to.
            slot (slot): The Gearset slot being equipped to.

        Returns:
            equip (bool): Whether to equip it or not.
        """
        return True

    def at_before_get(self, entity, inventory):
        """
        This is called whenever the owner wants to get an item.
        If it returns false, the item will not be obtained.
        Override this hook to implement Aspect-specified rules
        about who can carry what.

        Args:
            entity (Entity): The item being nabbed.
            inventory (Inventory): The proposed destination inventory.

        Returns:
            get (bool): Whether to get it or not.
        """
        return True
