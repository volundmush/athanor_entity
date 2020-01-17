from django.conf import settings

from evennia.utils.utils import class_from_module
from athanor.gamedb.objects import AthanorObject

MIXINS = []

for mixin in settings.MIXINS["ENTITY_STRUCTURE"]:
    MIXINS.append(class_from_module(mixin))
MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


class AthanorStructure(*MIXINS, AthanorObject):
    pass
