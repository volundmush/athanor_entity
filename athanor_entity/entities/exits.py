from django.conf import settings
from evennia.utils.utils import class_from_module
from evennia.commands import cmdset
from evennia.objects.objects import ExitCommand

from athanor.entities.base import AbstractMapEntity

MIXINS = []

for mixin in settings.MIXINS["EXIT"]:
    MIXINS.append(class_from_module(mixin))
MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


class AthanorExit(*MIXINS, AbstractMapEntity):
    exit_command = ExitCommand
    priority = 101
    default_inventory = 'exits'

    def __init__(self, destination_key, handler, data, room):
        AbstractMapEntity.__init__(self, data.get("name"), handler, data)
        self.location = room
        self.db_destination = self.handler.rooms.get(destination_key, None)

        self.description = data.get("description", "")
        self.aliases = data.get('aliases', list())
        self.gateway = self.handler.gateways.get(data.get('gateway', None), None)
        if self.gateway:
            self.gateway.exits[self] = self.db_destination

    def create_exit_cmdset(self, exidbobj):
        cmd = self.exit_command(
            key=exidbobj.db_key.strip().lower(),
            aliases=exidbobj.aliases,
            locks=str(exidbobj.locks),
            auto_help=False,
            destination=exidbobj.db_destination,
            arg_regex=r"^$",
            is_exit=True,
            obj=exidbobj,
            gateway=exidbobj.gateway
        )
        exit_cmdset = cmdset.CmdSet(None)
        exit_cmdset.key = "ExitCmdSet"
        exit_cmdset.priority = self.priority
        exit_cmdset.duplicates = True
        exit_cmdset.add(cmd)
        return exit_cmdset

    def at_cmdset_get(self, **kwargs):
        """
        Called just before cmdsets on this object are requested by the
        command handler. If changes need to be done on the fly to the
        cmdset before passing them on to the cmdhandler, this is the
        place to do it. This is called also if the object currently
        has no cmdsets.

        Kwargs:
          force_init (bool): If `True`, force a re-build of the cmdset
            (for example to update aliases).

        """

        if "force_init" in kwargs or not self.cmdset.has_cmdset(
            "ExitCmdSet", must_be_default=True
        ):
            # we are resetting, or no exit-cmdset was set. Create one dynamically.
            self.cmdset.add_default(self.create_exit_cmdset(self), permanent=False)

    def at_init(self):
        """
        This is called when this objects is re-loaded from cache. When
        that happens, we make sure to remove any old ExitCmdSet cmdset
        (this most commonly occurs when renaming an existing exit)
        """
        self.cmdset.remove_default()

    def at_traverse(self, traversing_object, target_location, **kwargs):
        """
        This implements the actual traversal. The traverse lock has
        already been checked (in the Exit command) at this point.

        Args:
            traversing_object (Object): Object traversing us.
            target_location (Object): Where target is going.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        """
        source_location = traversing_object.location
        if traversing_object.move_to(target_location):
            self.at_after_traverse(traversing_object, source_location)
        else:
            self.at_failed_traverse(traversing_object)

    def at_failed_traverse(self, traversing_object, **kwargs):
        """
        Overloads the default hook to implement a simple default error message.

        Args:
            traversing_object (Object): The object that failed traversing us.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        Notes:
            Using the default exits, this hook will not be called if an
            Attribute `err_traverse` is defined - this will in that case be
            read for an error string instead.

        """
        traversing_object.msg("You cannot go there.")
