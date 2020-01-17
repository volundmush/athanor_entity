from django.conf import settings

from evennia.utils.utils import class_from_module
from athanor.gamedb.objects import AthanorObject
from athanor_entity.entities.base import BaseGameEntity

MIXINS = [class_from_module(mixin) for mixin in settings.MIXINS["ENTITY_STRUCTURE"]]
MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


class AthanorStructure(*MIXINS, BaseGameEntity, AthanorObject):
    pass
