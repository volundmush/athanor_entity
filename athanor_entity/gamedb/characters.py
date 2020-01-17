from django.conf import settings
from evennia.utils.utils import class_from_module
from athanor.gamedb.characters import AthanorPlayerCharacter

MIXINS = [class_from_module(mixin) for mixin in settings.MIXINS["ENTITY_CHARACTER"]]
MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


class EntityPlayerCharacter(*MIXINS, AthanorPlayerCharacter):
    persistent = True

    @property
    def contents(self):
        """
        This must return a list for commands to work properly.

        Returns:
            items (list)
        """
        return self.items.all()
