# This one should be loaded FIRST, period.
LOAD_PRIORITY = -1000000


def load(settings):

    settings.MIXINS["SESSION"].extend(["athanor_entity.mixins.sessions.EntitySessionMixin"])
    # The default fallback character typeclass should probably change.
    settings.BASE_CHARACTER_TYPECLASS = "athanor_entity.gamedb.characters.EntityPlayerCharacter"
    # Gotta provide a default starting spot for Entity characters.
    settings.ENTITY_DEFAULT_HOME = "limbo/limbo_room"
    settings.ENTITY_START_LOCATION = "limbo/limbo_room"
    settings.GLOBAL_SCRIPTS['gamedata'] = {'typeclass': 'athanor_entity.controllers.gamedata.AthanorGameDataController',
                                           'repeats': -1, 'interval': 50, 'desc': 'Controller for Data System'}
