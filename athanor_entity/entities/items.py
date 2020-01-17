from django.conf import settings
from evennia.utils.utils import class_from_module
from athanor_entity.entities.base import AthanorGameEntity


MIXINS = []

for mixin in settings.MIXINS["ENTITY_ITEM"]:
    MIXINS.append(class_from_module(mixin))
MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


class AthanorItem(AthanorGameEntity):
    pass
