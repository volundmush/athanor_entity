from django.conf import settings
from evennia.utils.utils import class_from_module
from athanor.entities.base import AthanorGameEntity

MIXINS = []

for mixin in settings.MIXINS["MOBILE"]:
    MIXINS.append(class_from_module(mixin))
MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


class AthanorMobile(*MIXINS, AthanorGameEntity):
    pass
