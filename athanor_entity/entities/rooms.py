from django.conf import settings
from evennia.utils.utils import class_from_module
from athanor.entities.base import AbstractMapEntity

MIXINS = []

for mixin in settings.MIXINS["ROOM"]:
    MIXINS.append(class_from_module(mixin))
MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


class AthanorRoom(*MIXINS, AbstractMapEntity):
    fixed = True

    def __init__(self, unique_key, handler, data):
        super().__init__(unique_key, handler, data)
        self.description = data.get("description", "")
        self.item_data = data.get('items', list())
        self.mobile_data = data.get('mobiles', list())
        self.exit_data = data.get('exits', dict())
        self.lock_storage = data.get("locks", "")
        area_key = data.get('area', None)
        self.area = handler.areas.get(area_key, None)
        if self.area:
            self.area.rooms.add(self)

    def load_items(self):
        pass

    def load_mobiles(self):
        pass

    def load_exits(self):
        for destination_key, exit_data in self.exit_data.items():
            exit_class = exit_data.get('class')
            exit_class(destination_key, self.handler, exit_data, self)

    def get_description(self, looker):
        return self.description
