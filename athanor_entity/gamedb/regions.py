from django.conf import settings

from evennia.utils.utils import lazy_property, class_from_module

from athanor.gamedb.objects import AthanorObject
from athanor_entity.models import RegionBridge, MapBridge

MIXINS = []

for mixin in settings.MIXINS["ENTITY_REGION"]:
    MIXINS.append(class_from_module(mixin))
MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


class AthanorRegion(*MIXINS, AthanorObject):

    def create_bridge(self, plugin, key, data):
        if hasattr(self, 'region_bridge'):
            return
        RegionBridge.objects.create(object=self, system_key=key)
        MapBridge.objects.create(object=self, plugin=plugin, map_key=data.get('map'))


    @classmethod
    def create_region(cls, extension, key, data, **kwargs):
        if RegionBridge.objects.filter(system_key=key).count():
            raise ValueError("Name conflicts with another Region.")
        region, errors = cls.create(key, **kwargs)
        if region:
            region.create_bridge(extension, key, data)
        else:
            raise ValueError(errors)
        return region

    def update_data(self, data):
        pass

    @lazy_property
    def entities(self):
        return set()

    def register_entity(self, entity):
        self.entities.add(entity)

    def unregister_entity(self, entity):
        self.entities.remove(entity)