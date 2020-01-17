# This one should be loaded FIRST, period.
LOAD_PRIORITY = -1000000


def load(settings):
    base_game = ['athanor_entity.entities.base.BaseGameEntity']
    for category in ("ENTITY_CHARACTER", "ENTITY_STRUCTURE", "ENTITY_REGION"):
        settings.MIXINS[category].extend(base_game)
    # The default fallback character typeclass should probably change.
    settings.BASE_CHARACTER_TYPECLASS = "athanor_entity.gamedb.characters.EntityPlayerCharacter"
    # Gotta provide a default starting spot for Entity characters.
    settings.ENTITY_DEFAULT_HOME = "limbo/limbo_room"
    settings.ENTITY_START_LOCATION = "limbo/limbo_room"
    settings.GLOBAL_SCRIPTS['gamedata'] = {'typeclass': 'athanor_entity.controllers.gamedata.AthanorGameDataController',
                                           'repeats': -1, 'interval': 50, 'desc': 'Controller for Data System'}
