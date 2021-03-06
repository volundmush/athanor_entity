from django.conf import settings
from evennia.utils.utils import class_from_module
from athanor_entity.entities.base import AbstractMapEntity

MIXINS = []

for mixin in settings.MIXINS["ENTITY_AREA"]:
    MIXINS.append(class_from_module(mixin))
MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


class AthanorArea(*MIXINS, AbstractMapEntity):

    def __init__(self, unique_key, handler, data):
        AbstractMapEntity.__init__(self, unique_key, handler, data)
        self.description = data.get("description", "")
        self.rooms = set()
