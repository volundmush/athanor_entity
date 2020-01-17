from django.conf import settings
from evennia import GLOBAL_SCRIPTS
from evennia.utils.utils import class_from_module
from evennia.objects.objects import ObjectSessionHandler


class KeywordHandler(object):

    def __init__(self, owner):
        self.owner = owner

    def all(self, looker=None):
        pass


class BodyHandler(object):

    @property
    def persistent(self):
        return self.owner.persistent

    def __init__(self, owner):
        self.owner = owner
        self.forms = dict()
        self.active = None


class AspectHandler(object):

    def __init__(self, owner):
        self.owner = owner
        self.aspects = dict()

    def all(self):
        return self.aspects.values()


class ItemHandler(object):

    def __init__(self, owner):
        self.owner = owner
        self.inventories = dict()

    @property
    def contents(self):
        all = set()
        for inv in self.inventories.values():
            all += inv.contents
        return list(all)

    def all(self, inv_name=None):
        if not inv_name:
            return self.contents
        else:
            if inv_name in self.inventories:
                return self.inventories[inv_name].all()
            else:
                return list()

    def get_inventory(self, inv_name):
        if (found := self.inventories.get(inv_name, None)):
            return found
        inv_class = class_from_module(settings.SPECIAL_INVENTORY_CLASSES.get(inv_name, settings.BASE_INVENTORY_CLASS))
        new_inv = inv_class(self, inv_name)
        self.inventories[inv_name] = new_inv
        return new_inv

    def can_add(self, entity, inv_name):
        if entity in self.contents:
            raise ValueError(f"{self.owner} is already carrying {entity}!")
        inv = self.get_inventory(inv_name)
        for aspect in self.owner.aspects.all():
            if not aspect.at_before_get(entity, inv):
                raise ValueError(f"{aspect} does not allow getting {entity}!")
        inv.can_add(entity)

    def can_transfer(self, entity, inv_name):
        if entity not in self.contents:
            raise ValueError(f"{self.owner} is not carrying {entity}!")
        old_inv = entity.inventory_location
        old_inv.can_remove(entity)
        inv = self.get_inventory(inv_name)
        inv.can_add(entity)

    def can_remove(self, entity):
        if entity not in self.contents:
            raise ValueError(f"{self.owner} is not carrying {entity}!")
        old_inv = entity.inventory_location
        old_inv.can_remove(entity)

    def add(self, entity, inv_name=None, run_checks=True):
        if not inv_name:
            inv_name = entity.default_inventory
        if run_checks:
            self.can_add(entity, inv_name)
        inv = self.get_inventory(inv_name)
        inv.add(entity)
        self.contents.add(entity)

    def transfer(self, entity, inv_name, run_checks=True):
        if run_checks:
            self.can_transfer(entity, inv_name)
        dest = self.get_inventory(inv_name)
        inv = entity.inventory_location
        inv.remove(entity)
        dest.add(entity)

    def remove(self, entity, run_checks=True):
        if run_checks:
            self.can_remove(entity)
        inv = entity.inventory_location
        inv.remove(entity)
        self.contents.remove(entity)


class EquipRequest(object):

    def __init__(self, handler, entity, gearset=None, gearset_name=None, gearslot=None, gearslot_name=None, layer=None):
        self.handler = handler
        self.equipper = handler.owner
        self.entity = entity
        self.gearset = gearset
        self.gearset_name = gearset_name
        self.gearslot = gearslot
        self.gearslot_name = gearslot_name
        self.layer = layer
        self.process()

    def process(self):
        if not self.gearset:
            if not self.gearset_name:
                self.gearset_name = self.entity.default_gearset
            if not self.gearset_name:
                raise ValueError(f"{self.entity} cannot be equipped: No GearSet to equip it to.")
            self.gearset = self.handler.get_gearset(self.gearset_name)

        if not self.gearslot:
            if not self.gearslot_name:
                self.gearslot_name = self.entity.default_gearslot
            if not self.gearslot_name:
                raise ValueError(f"{self.entity} cannot be equipped: No GearSlot is available for {self.gearset}!")
            self.gearslot = self.gearset.get_gearslot(self.gearslot_name)

        # Remember, layer 0 is a totally viable layer. We can't just check for False here.
        self.layer = self.gearslot.available_layer(self.layer)
        if self.layer is None:
            raise ValueError(f"{self.gearslot} has no available layers!")


class GearHandler(object):

    def __init__(self, owner):
        self.owner = owner
        self.gearsets = dict()
        self.contents = set()

    @property
    def equipped(self):
        all = set()
        for inv in self.gearsets.values():
            all += inv.equipped
        return list(all)

    def all(self, gearset_name=None):
        if not gearset_name:
            return list(self.contents)
        else:
            if gearset_name in self.gearsets:
                return self.gearsets[gearset_name].all()
            else:
                return list()

    def get_gearset(self, set_name):
        if (found := self.gearsets.get(set_name, None)):
            return found
        inv_class = class_from_module(settings.SPECIAL_GEARSET_CLASSES.get(set_name, settings.BASE_GEARSET_CLASS))
        new_inv = inv_class(self, set_name)
        self.gearsets[set_name] = new_inv
        return new_inv

    def can_equip(self, entity):
        if entity in self.contents:
            raise ValueError(f"{entity} is already equipped by {self.owner}!")
        if entity not in self.owner.items.contents:
            raise ValueError(f"{self.owner} is not carrying {entity}!")
        entity.inventory_location.can_remove(entity)

    def equip(self, entity, set_name=None, set_slot=None, set_layer=None, run_checks=True):
        if run_checks:
            self.can_equip(entity)
        request = EquipRequest(self, entity, gearset_name=set_name, gearslot_name=set_slot, layer=set_layer)
        if run_checks:
            for aspect in self.owner.aspects.all():
                if not aspect.at_before_equip(entity, request):
                    raise ValueError(f"{aspect} does not allow equipping {entity}!")
        self.owner.items.remove(entity)
        request.gearset.equip(request)
        self.contents.add(entity)

    def can_unequip(self, entity):
        if entity not in self.contents:
            raise ValueError(f"{self.owner} is not using {entity}!")
        old_gear = entity.equip_location
        old_gear.can_unequip(entity)

    def unequip(self, entity, inv_name=None, run_checks=True):
        if run_checks:
            self.can_unequip(entity)
            self.owner.items.can_add(entity, inv_name)
        gear = entity.equip_location
        gear.remove(entity)
        self.contents.remove(entity)
        self.owner.items.add(entity, inv_name, run_checks=False)


class MapHandler(object):

    def __init__(self, owner):
        self.owner = owner
        self.rooms = dict()
        self.gateways = dict()
        self.areas = dict()
        self.loaded = False

    def get_room(self, room_key):
        if not self.loaded:
            self.load()
        return self.rooms.get(room_key, None)

    def load(self):
        if self.loaded:
            return
        if not hasattr(self.owner, 'map_bridge'):
            raise ValueError(f"{self.owner} does not support an internal map!")
        bri = self.owner.map_bridge
        if not (plugin := GLOBAL_SCRIPTS.plugin.ndb.plugins.get(bri.plugin, None)):
            raise ValueError(f"Cannot load {self.owner} map data: {bri.plugin} extension not found.")
        if not (inst := plugin.maps.get(bri.map_key, None)):
            raise ValueError(
                f"Cannot load {self.owner} map data: {bri.plugin}/{bri.map_key} map not found.")

        inst_data = inst.get('map', dict())

        for area_key, area_data in inst.get('areas', dict()).items():
            area_class = area_data.get('class')
            self.areas[area_key] = area_class(area_key, self, area_data)

        for room_key, room_data in inst.get('rooms', dict()).items():
            room_class = room_data.get('class')
            self.rooms[room_key] = room_class(room_key, self, room_data)

        for gateway_key, gateway_data in inst.get('gateways', dict()).items():
            gateway_class = gateway_data.get('class')
            self.gateways[gateway_key] = gateway_class(gateway_key, self, gateway_data)

        for room in self.rooms.values():
            room.load_exits()

        self.loaded = True

    def save(self):
        pass


class LocationHandler(object):

    def __init__(self, owner):
        self.owner = owner
        self.room = None
        self.x = None
        self.y = None
        self.z = None

    @property
    def map(self):
        if not self.room:
            return None
        return self.room.handler.owner

    def set(self, room, save=True):
        if isinstance(room, str):
            room = GLOBAL_SCRIPTS.plugin.resolve_room_path(room)
        if room and not hasattr(room, 'map'):
            return
            # raise ValueError(f"{room} is not a valid location for a game entity.")
        if room and room == self.room:
            return
        old_room = self.room
        if old_room:
            old_room.entities.remove(self.owner)
            old_room.at_unregister_entity(self.owner)
            if not room or room.handler.owner != old_room.handler.owner:
                old_room.handler.owner.entities.remove(self.owner)
                old_room.handler.owner.at_unregister_entity(self.owner)
        self.room = room
        if room:
            if not old_room or old_room.map != room.map:
                room.handler.owner.entities.add(self.owner)
                room.handler.owner.at_register_entity(self.owner)
            room.entities.add(self.owner)
            room.at_register_entity(self.owner)
        if room and save and room.fixed:
            self.save()

    def save(self, name="logout"):
        if not self.owner.persistent:
            return
        if not self.room:
            return
        if not self.room.fixed:
            raise ValueError("Cannot save to a non-fixed room.")
        if (loc := self.owner.saved_locations.filter(name=name).first()):
            loc.map = self.map
            loc.room_key = self.room.unique_key
            loc.x_coordinate = self.x
            loc.y_coordinate = self.y
            loc.z_coordinate = self.z
            loc.save()
        else:
            self.owner.saved_locations.create(name=name, map=self.map, room_key=self.room.unique_key,
                                              x_coordinate=self.x, y_coordinate=self.y, z_coordinate=self.z)

    def recall(self, name="logout"):
        if not self.owner.persistent:
            return
        if not (loc := self.owner.saved_locations.filter(name=name).first()):
            raise ValueError(f"No saved location for {name}")
        self.owner.move_to(loc.map.map.get_room(loc.room_key))


class FactionHandler(object):

    def __init__(self, owner):
        self.owner = owner

    def is_member(self, faction, check_admin=True):

        def recursive_check(fact):
            checking = fact
            while checking:
                if checking == faction:
                    return True
                checking = checking.db_parent
            return False

        if hasattr(faction, 'faction_bridge'):
            faction = faction.faction_bridge
        if check_admin and self.owner.is_admin():
            return True
        if self.factions.filter(db_faction=faction).count():
            return True
        all_factions = self.factions.all()
        for fac in all_factions:
            if recursive_check(fac.db_faction):
                return True
        return False


class AllianceHandler(object):

    def __init__(self, owner):
        self.owner = owner


class DivisionHandler(object):

    def __init__(self, owner):
        self.owner = owner
