from athanor_entity.entities.base import BaseGameEntity


class EntitySessionMixin(object):

    def mixin_at_sync(self):
        if self.puppet and isinstance(self.puppet, BaseGameEntity) and self.puppet.persistent and self.puppet.location is None:
            self.puppet.locations.recall()