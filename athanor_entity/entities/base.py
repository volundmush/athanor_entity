import datetime, re, time
from django.conf import settings
from collections import defaultdict

from evennia.utils import ansi
from evennia.utils.utils import time_format, logger, lazy_property, make_iter, to_str, is_iter, list_to_string
from evennia.utils.utils import class_from_module
from evennia.utils.ansi import ANSIString
from evennia.commands.cmdsethandler import CmdSetHandler
from evennia.locks.lockhandler import LockHandler
from evennia.typeclasses.tags import Tag, TagHandler, AliasHandler, PermissionHandler
from evennia.objects.objects import _INFLECT
from evennia.commands import cmdhandler
from evennia.objects.objects import ObjectSessionHandler

from athanor.utils.mixins import HasLocks, HasInventory
from athanor.entities.handlers import GearHandler, ItemHandler, AspectHandler, KeywordHandler
from athanor.entities.handlers import LocationHandler, MapHandler
from athanor.entities.handlers import FactionHandler, AllianceHandler, DivisionHandler
from athanor.utils.color import green_yellow_red, red_yellow_green
from athanor.utils.time import utcnow
from athanor.utils.text import partial_match

from django.utils.translation import ugettext as _

_PERMISSION_HIERARCHY = [p.lower() for p in settings.PERMISSION_HIERARCHY]


BASE_MIXINS = []

for mixin in settings.MIXINS["BASE"]:
    BASE_MIXINS.append(class_from_module(mixin))
BASE_MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


ENTITY_MIXINS = []

for mixin in settings.MIXINS["ENTITY"]:
    ENTITY_MIXINS.append(class_from_module(mixin))
ENTITY_MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


MAPENT_MIXINS = []

for mixin in settings.MIXINS["MAPENT"]:
    MAPENT_MIXINS.append(class_from_module(mixin))
MAPENT_MIXINS.sort(key=lambda x: getattr(x, "mixin_priority", 0))


class AbstractGameEntity(*BASE_MIXINS, HasInventory):
    """
    This class is not meant to be used directly. It forms the foundation for Athanor's Entity system,
    providing new Handlers and additional hook and logics for use by both Athanor Entities and Athanor sub-classes
    of Evennia's DefauultObject.

    Simply adding this as a mixin to something like DefaultCharacter is not enough.
    Custom edits are needed to objects that inherit from DefaultObject to make them co-exist with Entities.

    This has nothing that DefaultObject already implements, only stuff that must be ADDED to it.
    """
    persistent = False
    re_search = re.compile(r"^(?i)(?P<choice>(all|[0-9]+)\.)?(?P<search>.*)?")

    @lazy_property
    def locations(self):
        return LocationHandler(self)

    @lazy_property
    def entities(self):
        return set()

    def at_register_entity(self, entity):
        pass

    def at_unregister_entity(self, entity):
        pass

    @lazy_property
    def aspects(self):
        return AspectHandler(self)

    @lazy_property
    def map(self):
        return MapHandler(self)

    @lazy_property
    def gear(self):
        return GearHandler(self)

    @lazy_property
    def items(self):
        return ItemHandler(self)

    @lazy_property
    def factions(self):
        return FactionHandler(self)

    @lazy_property
    def divisions(self):
        return DivisionHandler(self)

    @lazy_property
    def alliances(self):
        return AllianceHandler(self)

    @lazy_property
    def keywords(self):
        return KeywordHandler(self)

    def get_gender(self, looker):
        return "neuter"

    def system_msg(self, *args, **kwargs):
        if hasattr(self, 'account'):
            self.account.system_msg(*args, **kwargs)

    def pretty_idle_time(self, override=None):
        idle_time = override if override is not None else self.idle_time
        color_cutoff_seconds = 3600
        value = 0
        if idle_time <= color_cutoff_seconds:
            value = (color_cutoff_seconds // idle_time) * 100
        return ANSIString(f"|{red_yellow_green(value)}{time_format(idle_time, style=1)}|n")

    def pretty_conn_time(self, override=None):
        conn_time = override if override is not None else self.connection_time
        return ANSIString(f"|{red_yellow_green(100)}{time_format(conn_time, style=1)}|n")

    def get_last_logout(self):
        return utcnow()

    def pretty_last_time(self, viewer, time_format='%b %m'):
        return ANSIString(f"|x{viewer.localize_timestring(self.get_last_logout(), time_format=time_format)}|n")

    def idle_or_last(self, viewer, time_format='%b %m'):
        if self.sessions.all() and self.conn_visible_to(viewer):
            return self.pretty_idle_time()
        return self.pretty_last_time(viewer, time_format)

    def conn_or_last(self, viewer, time_format='%b %m'):
        if self.sessions.all() and self.conn_visible_to(viewer):
            return self.pretty_conn_time()
        return self.pretty_last_time(viewer, time_format)

    def idle_or_off(self, viewer):
        if self.sessions.all() and self.conn_visible_to(viewer):
            return self.pretty_idle_time()
        return '|XOff|n'

    def conn_or_off(self, viewer):
        if self.sessions.all() and self.conn_visible_to(viewer):
            return self.pretty_conn_time()
        return '|XOff|n'

    def conn_visible_to(self, viewer):
        if self.is_conn_hidden():
            return self.access(viewer, 'see_hidden', default="perm(Admin)")
        return True

    def is_conn_hidden(self):
        return False

    def localize_timestring(self, time_data, time_format='%x %X'):
        if hasattr(self, 'account'):
            return self.account.localize_timestring(time_data, time_format)
        return time_data.astimezone(datetime.timezone.utc).strftime(time_format)

    @property
    def idle_time(self):
        """
        Returns the idle time of the least idle session in seconds. If
        no sessions are connected it returns nothing.
        """
        idle = [session.cmd_last_visible for session in self.sessions.all()]
        if idle:
            return time.time() - float(max(idle))
        return None

    @property
    def connection_time(self):
        """
        Returns the maximum connection time of all connected sessions
        in seconds. Returns nothing if there are no sessions.
        """
        conn = [session.conn_time for session in self.sessions.all()]
        if conn:
            return time.time() - float(min(conn))
        return None

    def search_entities(self, searchdata, candidates=None, allow_here=True,  allow_me=True, allow_all=True):

        if allow_here and searchdata.lower() in ("here",):
            return [self.location]
        if allow_me and searchdata.lower() in ("me", "self"):
            return [self]
        if allow_all and searchdata.lower() in ('all'):
            return candidates

        if not candidates:
            candidates = self.contents
            if self.location:
                candidates += self.location.contents
                candidates.remove(self)

        process_search = self.re_search.match(searchdata).groupdict()

        if not (search := process_search.get('search', None)):
            raise ValueError("Must enter some text to search for!")

        search = search.strip()

        choice = process_search.get('choice', None)

        if choice:
            if choice.isdigit():
                choice = int(choice) - 1
            elif choice.lower() == "all":
                choice = "all"
        else:
            choice = 0

        keywords = defaultdict(list)
        for ent in candidates:
            for keyword in ent.keywords.all(looker=self):
                keywords[keyword.strip()].append(ent)

        if not (found := partial_match(search, keywords.keys())):
            raise ValueError(f"Nothing around here that looks like a {search}!")

        ents = keywords.get(found, list())
        if choice == "all":
            return ents
        if choice > len(ents):
            raise ValueError(f"There isn't a {choice} {search} here to target!")
        return [ents[choice]]

    def at_entity_change(self):
        """
        Hook that's called when something changes regarding this entity, like stats
        or durability.

        This will make sure that any relevant code calls are made to make sure
        this change persists, if needed.

        Returns:
            None
        """
        if self.inventory_location:
            self.inventory_location.update(self)
        if self.gear_location:
            self.gear_location.update(self)


    def move_to(self, destination, quiet=False, emit_to_obj=None, use_destination=False, to_none=False, move_hooks=True,
                **kwargs):
        """
        Re-implementation of Evennia's move_to to account for the new grid. See original documentation.

        Destination MUST be in the format of:
        1. A Room object.
        2. None
        3. #DBREF/room_key - For structures. example: #5/docking_bay
        4. region_key/room_key - For example, limbo_dimension/northern_limbo

        use_destination will be ignored.
        """
        def logerr(string="", err=None):
            """Simple log helper method"""
            logger.log_trace()
            self.msg("%s%s" % (string, "" if err is None else " (%s)" % err))
            return

        errtxt = _("Couldn't perform move ('%s'). Contact an admin.")
        if not emit_to_obj:
            emit_to_obj = self

        if not destination:
            if to_none:
                # immediately move to None. There can be no hooks called since
                # there is no destination to call them with.
                self.location = None
                return True
            emit_to_obj.msg(_("The destination doesn't exist."))
            return False
        if use_destination and hasattr(destination, 'destination'):
            # traverse exits
            # destination = destination.destination
            pass

        if isinstance(destination, str):
            from evennia import GLOBAL_SCRIPTS
            destination = GLOBAL_SCRIPTS.plugin.resolve_room_path(destination)

        # Before the move, call eventual pre-commands.
        if move_hooks:
            try:
                if not self.at_before_move(destination):
                    return False
            except Exception as err:
                logerr(errtxt % "at_before_move()", err)
                return False

        # Save the old location
        source_location = self.location

        # Call hook on source location
        if move_hooks and source_location:
            try:
                source_location.at_object_leave(self, destination)
            except Exception as err:
                logerr(errtxt % "at_object_leave()", err)
                return False

        if not quiet:
            # tell the old room we are leaving
            try:
                self.announce_move_from(destination, **kwargs)
            except Exception as err:
                logerr(errtxt % "at_announce_move()", err)
                return False

        # Perform move
        try:
            self.location = destination
        except Exception as err:
            logerr(errtxt % "location change", err)
            return False

        if not quiet:
            # Tell the new room we are there.
            try:
                self.announce_move_to(source_location, **kwargs)
            except Exception as err:
                logerr(errtxt % "announce_move_to()", err)
                return False

        if move_hooks:
            # Perform eventual extra commands on the receiving location
            # (the object has already arrived at this point)
            try:
                destination.at_object_receive(self, source_location)
            except Exception as err:
                logerr(errtxt % "at_object_receive()", err)
                return False

        # Execute eventual extra commands on this object after moving it
        # (usually calling 'look')
        if move_hooks:
            try:
                self.at_after_move(source_location)
            except Exception as err:
                logerr(errtxt % "at_after_move", err)
                return False
        return True

    @property
    def location(self):
        return self.locations.room

    @location.setter
    def location(self, value):
        self.locations.set(value)


class AthanorGameEntity(*ENTITY_MIXINS, HasLocks, AbstractGameEntity):
    """
    This class builds on AbstractGameEntity, re-implementing much of DefaultObject's features.
    """
    persistent = False
    _is_deleted = False

    def __init__(self, data):
        self.id = -1
        self.db_key = data.get("name", "Unknown Entity")
        self.db_lock_storage = data.get('locks', "")
        self.db_cmdset_storage = data.get('cmdsets', "")
        self.db_account = None
        self.db_sessid = ""
        self.db_date_created = data.get("date_created", utcnow())
        self.db_typeclass_path = data.get('typeclass_path', '')
        self.db_home = None
        self.db_destination = None
        self.inventory_location = None
        self.gear_location = None

    def __str__(self):
        return self.db_key

    def __repr__(self):
        return self.db_key

    @lazy_property
    def dbref(self):
        return f"#{self.id}"

    @property
    def account(self):
        return self.db_account

    @account.setter
    def account(self, value):
        self.db_account = value

    @property
    def sessid(self):
        return self.db_sessid

    @sessid.setter
    def sessid(self, value):
        self.db_sessid = value

    @property
    def name(self):
        return self.db_key

    @property
    def key(self):
        return self.db_key

    @key.setter
    def key(self, value):
        self.db_key = value

    @property
    def date_created(self):
        return self.db_date_created

    @date_created.setter
    def date_created(self, value):
        self.db_date_created = value

    def contents_get(self, exclude=None):
        contents = self.contents
        if exclude:
            for entity in make_iter(exclude):
                if entity in contents:
                    contents.remove(entity)
        return contents

    def get_display_name(self, looker, **kwargs):
        return self.name

    def get_numbered_name(self, count, looker, **kwargs):
        key = kwargs.get("key", self.key)
        key = ansi.ANSIString(
            key
        )  # this is needed to allow inflection of colored names
        plural = _INFLECT.plural(key, 2)
        plural = "%s %s" % (_INFLECT.number_to_words(count, threshold=12), plural)
        singular = _INFLECT.an(key)
        if not self.aliases.get(plural, category="plural_key"):
            # we need to wipe any old plurals/an/a in case key changed in the interrim
            self.aliases.clear(category="plural_key")
            self.aliases.add(plural, category="plural_key")
            # save the singular form as an alias here too so we can display "an egg" and also
            # look at 'an egg'.
            self.aliases.add(singular, category="plural_key")
        return singular, plural

    @property
    def typeclass_path(self):
        return self.db_typeclass_path

    @typeclass_path.setter
    def typeclass_path(self, value):
        self.db_typeclass_path = value

    # cmdset_storage property handling
    def __cmdset_storage_get(self):
        """getter"""
        storage = self.db_cmdset_storage
        return [path.strip() for path in storage.split(",")] if storage else []

    def __cmdset_storage_set(self, value):
        """setter"""
        self.db_cmdset_storage = ",".join(str(val).strip() for val in make_iter(value))

    def __cmdset_storage_del(self):
        """deleter"""
        self.db_cmdset_storage = None

    cmdset_storage = property(
        __cmdset_storage_get, __cmdset_storage_set, __cmdset_storage_del
    )

    @lazy_property
    def locks(self):
        return LockHandler(self)



    @property
    def contents(self):
        return self.items.all() + list(self.entities) + list(self.exits)

    @property
    def destination(self):
        return self.db_destination

    @destination.setter
    def destination(self, value):
        self.db_destination = value

    @property
    def exits(self):
        return list()

    @lazy_property
    def cmdset(self):
        return CmdSetHandler(self, True)

    @lazy_property
    def aliases(self):
        return AliasHandler(self)

    @lazy_property
    def permissions(self):
        return PermissionHandler(self)

    def access(
        self, accessing_obj, access_type="read", default=False, no_superuser_bypass=False, **kwargs
    ):
        """
        Determines if another object has permission to access this one.

        Args:
            accessing_obj (str): Object trying to access this one.
            access_type (str, optional): Type of access sought.
            default (bool, optional): What to return if no lock of
                access_type was found
            no_superuser_bypass (bool, optional): Turn off the
                superuser lock bypass (be careful with this one).

        Kwargs:
            kwargs (any): Ignored, but is there to make the api
                consistent with the object-typeclass method access, which
                use it to feed to its hook methods.

        """
        return self.locks.check(
            accessing_obj,
            access_type=access_type,
            default=default,
            no_superuser_bypass=no_superuser_bypass,
        )

    def check_permstring(self, permstring):
        if hasattr(self, "account"):
            if (
                    self.account
                    and self.account.is_superuser
                    and not self.account.attributes.get("_quell")
            ):
                return True
        else:
            if self.is_superuser and not self.attributes.get("_quell"):
                return True

        if not permstring:
            return False
        perm = permstring.lower()
        perms = [p.lower() for p in self.permissions.all()]
        if perm in perms:
            # simplest case - we have a direct match
            return True
        if perm in _PERMISSION_HIERARCHY:
            # check if we have a higher hierarchy position
            ppos = _PERMISSION_HIERARCHY.index(perm)
            return any(
                True
                for hpos, hperm in enumerate(_PERMISSION_HIERARCHY)
                if hperm in perms and hpos > ppos
            )
        # we ignore pluralization (english only)
        if perm.endswith("s"):
            return self.check_permstring(perm[:-1])

        return False

    @property
    def is_superuser(self):
        return False

    def return_appearance(self, looker, **kwargs):
        """
        This formats a description. It is the hook a 'look' command
        should call.

        Args:
            looker (Object): Object doing the looking.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).
        """
        if not looker:
            return ""
        # get and identify all objects
        visible = (
            con for con in self.contents if con != looker and con.access(looker, "view")
        )
        exits, users, things = [], [], defaultdict(list)
        for con in visible:
            key = con.get_display_name(looker)
            if con.destination:
                exits.append(key)
            elif con.has_account:
                users.append("|c%s|n" % key)
            else:
                # things can be pluralized
                things[key].append(con)
        # get description, build string
        string = "|c%s|n\n" % self.get_display_name(looker)
        desc = self.db.desc
        if desc:
            string += "%s" % desc
        if exits:
            string += "\n|wExits:|n " + list_to_string(exits)
        if users or things:
            # handle pluralization of things (never pluralize users)
            thing_strings = []
            for key, itemlist in sorted(things.items()):
                nitem = len(itemlist)
                if nitem == 1:
                    key, _ = itemlist[0].get_numbered_name(nitem, looker, key=key)
                else:
                    key = [
                        item.get_numbered_name(nitem, looker, key=key)[1]
                        for item in itemlist
                    ][0]
                thing_strings.append(key)

            string += "\n|wYou see:|n " + list_to_string(users + thing_strings)

        return string

    def at_look(self, target, **kwargs):
        """
        Called when this object performs a look. It allows to
        customize just what this means. It will not itself
        send any data.

        Args:
            target (Object): The target being looked at. This is
                commonly an object or the current location. It will
                be checked for the "view" type access.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call. This will be passed into
                return_appearance, get_display_name and at_desc but is not used
                by default.

        Returns:
            lookstring (str): A ready-processed look string
                potentially ready to return to the looker.

        """
        if not target.access(self, "view"):
            try:
                return "Could not view '%s'." % target.get_display_name(self, **kwargs)
            except AttributeError:
                return "Could not view '%s'." % target.key

        description = target.return_appearance(self, **kwargs)

        # the target's at_desc() method.
        # this must be the last reference to target so it may delete itself when acted on.
        target.at_desc(looker=self, **kwargs)

        return description

    def at_desc(self, looker=None, **kwargs):
        """
        This is called whenever someone looks at this object.

        Args:
            looker (Object, optional): The object requesting the description.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        """
        pass

    def execute_cmd(self, raw_string, session=None, **kwargs):
        raw_string = self.nicks.nickreplace(raw_string, categories=("inputline", "channel"), include_account=True)
        return cmdhandler.cmdhandler(self, raw_string, callertype="object", session=session, **kwargs)

    def msg(self, text=None, from_obj=None, session=None, options=None, **kwargs):
        # try send hooks
        if from_obj:
            for obj in make_iter(from_obj):
                try:
                    obj.at_msg_send(text=text, to_obj=self, **kwargs)
                except Exception:
                    logger.log_trace()
        kwargs["options"] = options
        try:
            if not self.at_msg_receive(text=text, **kwargs):
                # if at_msg_receive returns false, we abort message to this object
                return
        except Exception:
            logger.log_trace()

        if text is not None:
            if not (isinstance(text, str) or isinstance(text, tuple)):
                # sanitize text before sending across the wire
                try:
                    text = to_str(text)
                except Exception:
                    text = repr(text)
            kwargs['text'] = text

        # relay to session(s)
        sessions = make_iter(session) if session else self.sessions.all()
        for session in sessions:
            session.data_out(**kwargs)

    def save(self, *args, **kwargs):
        pass

    @lazy_property
    def sessions(self):
        return ObjectSessionHandler(self)

    @property
    def is_connected(self):
        # we get an error for objects subscribed to channels without this
        if self.account:  # seems sane to pass on the account
            return self.account.is_connected
        else:
            return False

    @property
    def has_account(self):
        return self.sessions.count()

    def msg_contents(self, text=None, exclude=None, from_obj=None, mapping=None, **kwargs):
        # we also accept an outcommand on the form (message, {kwargs})
        is_outcmd = text and is_iter(text)
        inmessage = text[0] if is_outcmd else text
        outkwargs = text[1] if is_outcmd and len(text) > 1 else {}

        contents = self.contents
        if exclude:
            exclude = make_iter(exclude)
            contents = [obj for obj in contents if obj not in exclude]
        for obj in contents:
            if mapping:
                substitutions = {t: sub.get_display_name(obj)
                                 if hasattr(sub, 'get_display_name')
                                 else str(sub) for t, sub in mapping.items()}
                outmessage = inmessage.format(**substitutions)
            else:
                outmessage = inmessage
            obj.msg(text=(outmessage, outkwargs), from_obj=from_obj, **kwargs)

    def for_contents(self, func, exclude=None, **kwargs):
        """
        Runs a function on every object contained within this one.

        Args:
            func (callable): Function to call. This must have the
                formal call sign func(obj, **kwargs), where obj is the
                object currently being processed and `**kwargs` are
                passed on from the call to `for_contents`.
            exclude (list, optional): A list of object not to call the
                function on.

        Kwargs:
            Keyword arguments will be passed to the function for all objects.
        """
        contents = self.contents
        if exclude:
            exclude = make_iter(exclude)
            contents = [obj for obj in contents if obj not in exclude]
        for obj in contents:
            func(obj, **kwargs)


    def clear_exits(self):
        """
        Destroys all of the exits and any exits pointing to this
        object as a destination.
        """
        pass

    def clear_contents(self):
        """
        Moves all objects (accounts/things) to their home location or
        to default home.
        """
        pass

    @classmethod
    def create(cls, key, account=None, **kwargs):
        """
        Creates a basic object with default parameters, unless otherwise
        specified or extended.

        Provides a friendlier interface to the utils.create_object() function.

        Args:
            key (str): Name of the new object.
            account (Account): Account to attribute this object to.

        Kwargs:
            description (str): Brief description for this object.
            ip (str): IP address of creator (for object auditing).

        Returns:
            object (Object): A newly created object of the given typeclass.
            errors (list): A list of errors in string form, if any.

        """
        errors = []
        obj = None

        # Get IP address of creator, if available
        ip = kwargs.pop('ip', '')

        # If no typeclass supplied, use this class
        kwargs['typeclass'] = kwargs.pop('typeclass', cls)

        # Set the supplied key as the name of the intended object
        kwargs['key'] = key

        # Get a supplied description, if any
        description = kwargs.pop('description', '')

        # Create a sane lockstring if one wasn't supplied
        lockstring = kwargs.get('locks')
        if account and not lockstring:
            lockstring = cls.lockstring.format(account_id=account.id)
            kwargs['locks'] = lockstring

        # Create object
        try:
            obj = create.create_object(**kwargs)

            # Record creator id and creation IP
            if ip: obj.db.creator_ip = ip
            if account: obj.db.creator_id = account.id

            # Set description if there is none, or update it if provided
            if description or not obj.db.desc:
                desc = description if description else "You see nothing special."
                obj.db.desc = desc

        except Exception as e:
            errors.append("An error occurred while creating this '%s' object." % key)
            logger.log_err(e)

        return obj, errors

    def copy(self, new_key=None, **kwargs):
        """
        Makes an identical copy of this object, identical except for a
        new dbref in the database. If you want to customize the copy
        by changing some settings, use ObjectDB.object.copy_object()
        directly.

        Args:
            new_key (string): New key/name of copied object. If new_key is not
                specified, the copy will be named <old_key>_copy by default.
        Returns:
            copy (Object): A copy of this object.

        """

        def find_clone_key():
            """
            Append 01, 02 etc to obj.key. Checks next higher number in the
            same location, then adds the next number available

            returns the new clone name on the form keyXX
            """
            key = self.key
            num = sum(1 for obj in self.location.contents
                      if obj.key.startswith(key) and obj.key.lstrip(key).isdigit())
            return "%s%03i" % (key, num)

        new_key = new_key or find_clone_key()
        new_obj = ObjectDB.objects.copy_object(self, new_key=new_key, **kwargs)
        self.at_object_post_copy(new_obj, **kwargs)
        return new_obj

    def at_object_post_copy(self, new_obj, **kwargs):
        """
        Called by DefaultObject.copy(). Meant to be overloaded. In case there's extra data not covered by
        .copy(), this can be used to deal with it.

        Args:
            new_obj (Object): The new Copy of this object.

        Returns:
            None
        """
        pass

    def delete(self):
        """
        Deletes this object.  Before deletion, this method makes sure
        to move all contained objects to their respective home
        locations, as well as clean up all exits to/from the object.

        Returns:
            noerror (bool): Returns whether or not the delete completed
                successfully or not.

        """
        global _ScriptDB
        if not _ScriptDB:
            from evennia.scripts.models import ScriptDB as _ScriptDB

        if not self.pk or not self.at_object_delete():
            # This object has already been deleted,
            # or the pre-delete check return False
            return False

        # See if we need to kick the account off.

        for session in self.sessions.all():
            session.msg(_("Your character %s has been destroyed.") % self.key)
            # no need to disconnect, Account just jumps to OOC mode.
        # sever the connection (important!)
        if self.account:
            # Remove the object from playable characters list
            if self in self.account.db._playable_characters:
                self.account.db._playable_characters = [x for x in self.account.db._playable_characters if x != self]
            for session in self.sessions.all():
                self.account.unpuppet_object(session)

        self.account = None

        for script in _ScriptDB.objects.get_all_scripts_on_obj(self):
            script.stop()

        # Destroy any exits to and from this room, if any
        self.clear_exits()
        # Clear out any non-exit objects located within the object
        self.clear_contents()
        self.attributes.clear()
        self.nicks.clear()
        self.aliases.clear()
        self.location = None  # this updates contents_cache for our location

        # Perform the deletion of the object
        super().delete()
        return True

    def at_first_save(self):
        """
        This is called by the typeclass system whenever an instance of
        this class is saved for the first time. It is a generic hook
        for calling the startup hooks for the various game entities.
        When overloading you generally don't overload this but
        overload the hooks called by this method.

        """
        pass

    def basetype_setup(self):
        """
        This sets up the default properties of an Object, just before
        the more general at_object_creation.

        You normally don't need to change this unless you change some
        fundamental things like names of permission groups.

        """
        # the default security setup fallback for a generic
        # object. Overload in child for a custom setup. Also creation
        # commands may set this (create an item and you should be its
        # controller, for example)

        self.locks.add(";".join([
            "control:perm(Developer)",  # edit locks/permissions, delete
            "examine:perm(Builder)",   # examine properties
            "view:all()",               # look at object (visibility)
            "edit:perm(Admin)",       # edit properties/attributes
            "delete:perm(Admin)",     # delete object
            "get:all()",                # pick up object
            "call:true()",              # allow to call commands on this object
            "tell:perm(Admin)",        # allow emits to this object
            "puppet:pperm(Developer)"]))  # lock down puppeting only to staff by default

    def basetype_posthook_setup(self):
        """
        Called once, after basetype_setup and at_object_creation. This
        should generally not be overloaded unless you are redefining
        how a room/exit/object works. It allows for basetype-like
        setup after the object is created. An example of this is
        EXITs, who need to know keys, aliases, locks etc to set up
        their exit-cmdsets.

        """
        pass

    def at_object_creation(self):
        """
        Called once, when this object is first created. This is the
        normal hook to overload for most object types.

        """
        pass

    def at_object_delete(self):
        """
        Called just before the database object is permanently
        delete()d from the database. If this method returns False,
        deletion is aborted.

        """
        return True

    def at_init(self):
        """
        This is always called whenever this object is initiated --
        that is, whenever it its typeclass is cached from memory. This
        happens on-demand first time the object is used or activated
        in some way after being created but also after each server
        restart or reload.

        """
        pass

    def at_cmdset_get(self, **kwargs):
        """
        Called just before cmdsets on this object are requested by the
        command handler. If changes need to be done on the fly to the
        cmdset before passing them on to the cmdhandler, this is the
        place to do it. This is called also if the object currently
        have no cmdsets.

        Kwargs:
            caller (Session, Object or Account): The caller requesting
                this cmdset.

        """
        pass

    def at_pre_puppet(self, account, session=None, **kwargs):
        """
        Called just before an Account connects to this object to puppet
        it.

        Args:
            account (Account): This is the connecting account.
            session (Session): Session controlling the connection.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        """
        pass

    def at_post_puppet(self, **kwargs):
        """
        Called just after puppeting has been completed and all
        Account<->Object links have been established.

        Args:
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).
        Note:
            You can use `self.account` and `self.sessions.get()` to get
            account and sessions at this point; the last entry in the
            list from `self.sessions.get()` is the latest Session
            puppeting this Object.

        """
        pass

    def at_pre_unpuppet(self, **kwargs):
        """
        Called just before beginning to un-connect a puppeting from
        this Account.

        Args:
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).
        Note:
            You can use `self.account` and `self.sessions.get()` to get
            account and sessions at this point; the last entry in the
            list from `self.sessions.get()` is the latest Session
            puppeting this Object.

        """
        pass

    def at_post_unpuppet(self, account, session=None, **kwargs):
        """
        Called just after the Account successfully disconnected from
        this object, severing all connections.

        Args:
            account (Account): The account object that just disconnected
                from this object.
            session (Session): Session id controlling the connection that
                just disconnected.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        """
        pass

    def at_server_reload(self):
        """
        This hook is called whenever the server is shutting down for
        restart/reboot. If you want to, for example, save non-persistent
        properties across a restart, this is the place to do it.

        """
        pass

    def at_server_shutdown(self):
        """
        This hook is called whenever the server is shutting down fully
        (i.e. not for a restart).

        """
        pass

    def at_access(self, result, accessing_obj, access_type, **kwargs):
        """
        This is called with the result of an access call, along with
        any kwargs used for that call. The return of this method does
        not affect the result of the lock check. It can be used e.g. to
        customize error messages in a central location or other effects
        based on the access result.

        Args:
            result (bool): The outcome of the access call.
            accessing_obj (Object or Account): The entity trying to gain access.
            access_type (str): The type of access that was requested.

        Kwargs:
            Not used by default, added for possible expandability in a
            game.

        """
        pass

    # hooks called when moving the object

    def at_before_move(self, destination, **kwargs):
        """
        Called just before starting to move this object to
        destination.

        Args:
            destination (Object): The object we are moving to
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        Returns:
            shouldmove (bool): If we should move or not.

        Notes:
            If this method returns False/None, the move is cancelled
            before it is even started.

        """
        # return has_perm(self, destination, "can_move")
        return True

    def announce_move_from(self, destination, msg=None, mapping=None, **kwargs):
        """
        Called if the move is to be announced. This is
        called while we are still standing in the old
        location.

        Args:
            destination (Object): The place we are going to.
            msg (str, optional): a replacement message.
            mapping (dict, optional): additional mapping objects.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        You can override this method and call its parent with a
        message to simply change the default message.  In the string,
        you can use the following as mappings (between braces):
            object: the object which is moving.
            exit: the exit from which the object is moving (if found).
            origin: the location of the object before the move.
            destination: the location of the object after moving.

        """
        if not self.location:
            return
        if msg:
            string = msg
        else:
            string = "{object} is leaving {origin}, heading for {destination}."

        location = self.location
        exits = [o for o in location.contents if o.location is location and o.destination is destination]
        if not mapping:
            mapping = {}

        mapping.update({
            "object": self,
            "exit": exits[0] if exits else "somewhere",
            "origin": location or "nowhere",
            "destination": destination or "nowhere",
        })

        location.msg_contents(string, exclude=(self, ), mapping=mapping)

    def announce_move_to(self, source_location, msg=None, mapping=None, **kwargs):
        """
        Called after the move if the move was not quiet. At this point
        we are standing in the new location.

        Args:
            source_location (Object): The place we came from
            msg (str, optional): the replacement message if location.
            mapping (dict, optional): additional mapping objects.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        Notes:
            You can override this method and call its parent with a
            message to simply change the default message.  In the string,
            you can use the following as mappings (between braces):
                object: the object which is moving.
                exit: the exit from which the object is moving (if found).
                origin: the location of the object before the move.
                destination: the location of the object after moving.

        """

        if not source_location and self.location.has_account:
            # This was created from nowhere and added to an account's
            # inventory; it's probably the result of a create command.
            string = "You now have %s in your possession." % self.get_display_name(self.location)
            self.location.msg(string)
            return

        if source_location:
            if msg:
                string = msg
            else:
                string = "{object} arrives to {destination} from {origin}."
        else:
            string = "{object} arrives to {destination}."

        origin = source_location
        destination = self.location
        exits = []
        if origin:
            exits = [o for o in destination.contents if o.location is destination and o.destination is origin]

        if not mapping:
            mapping = {}

        mapping.update({
            "object": self,
            "exit": exits[0] if exits else "somewhere",
            "origin": origin or "nowhere",
            "destination": destination or "nowhere",
        })

        destination.msg_contents(string, exclude=(self, ), mapping=mapping)

    def at_after_move(self, source_location, **kwargs):
        """
        Called after move has completed, regardless of quiet mode or
        not.  Allows changes to the object due to the location it is
        now in.

        Args:
            source_location (Object): Wwhere we came from. This may be `None`.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        """
        pass

    def at_object_leave(self, moved_obj, target_location, **kwargs):
        """
        Called just before an object leaves from inside this object

        Args:
            moved_obj (Object): The object leaving
            target_location (Object): Where `moved_obj` is going.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        """
        pass

    def at_object_receive(self, moved_obj, source_location, **kwargs):
        """
        Called after an object has been moved into this object.

        Args:
            moved_obj (Object): The object moved into this one
            source_location (Object): Where `moved_object` came from.
                Note that this could be `None`.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        """
        pass

    def at_traverse(self, traversing_object, target_location, **kwargs):
        """
        This hook is responsible for handling the actual traversal,
        normally by calling
        `traversing_object.move_to(target_location)`. It is normally
        only implemented by Exit objects. If it returns False (usually
        because `move_to` returned False), `at_after_traverse` below
        should not be called and instead `at_failed_traverse` should be
        called.

        Args:
            traversing_object (Object): Object traversing us.
            target_location (Object): Where target is going.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        """
        pass

    def at_after_traverse(self, traversing_object, source_location, **kwargs):
        """
        Called just after an object successfully used this object to
        traverse to another object (i.e. this object is a type of
        Exit)

        Args:
            traversing_object (Object): The object traversing us.
            source_location (Object): Where `traversing_object` came from.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        Notes:
            The target location should normally be available as `self.destination`.
        """
        pass

    def at_failed_traverse(self, traversing_object, **kwargs):
        """
        This is called if an object fails to traverse this object for
        some reason.

        Args:
            traversing_object (Object): The object that failed traversing us.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        Notes:
            Using the default exits, this hook will not be called if an
            Attribute `err_traverse` is defined - this will in that case be
            read for an error string instead.

        """
        pass

    def at_msg_receive(self, text=None, from_obj=None, **kwargs):
        """
        This hook is called whenever someone sends a message to this
        object using the `msg` method.

        Note that from_obj may be None if the sender did not include
        itself as an argument to the obj.msg() call - so you have to
        check for this. .

        Consider this a pre-processing method before msg is passed on
        to the user session. If this method returns False, the msg
        will not be passed on.

        Args:
            text (str, optional): The message received.
            from_obj (any, optional): The object sending the message.

        Kwargs:
            This includes any keywords sent to the `msg` method.

        Returns:
            receive (bool): If this message should be received.

        Notes:
            If this method returns False, the `msg` operation
            will abort without sending the message.

        """
        return True

    def at_msg_send(self, text=None, to_obj=None, **kwargs):
        """
        This is a hook that is called when *this* object sends a
        message to another object with `obj.msg(text, to_obj=obj)`.

        Args:
            text (str, optional): Text to send.
            to_obj (any, optional): The object to send to.

        Kwargs:
            Keywords passed from msg()

        Notes:
            Since this method is executed by `from_obj`, if no `from_obj`
            was passed to `DefaultCharacter.msg` this hook will never
            get called.

        """
        pass

    def get_description(self, looker):
        return f"{self} has no description!"

    def return_appearance(self, looker, **kwargs):
        """
        This formats a description. It is the hook a 'look' command
        should call.

        Args:
            looker (Object): Object doing the looking.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).
        """
        if not looker:
            return ""
        # get and identify all objects
        visible = (con for con in self.contents if con != looker and
                   con.access(looker, "view"))
        exits, users, things = [], [], defaultdict(list)
        for con in visible:
            key = con.get_display_name(looker)
            if con.destination:
                exits.append(key)
            elif con.has_account:
                users.append("|c%s|n" % key)
            else:
                # things can be pluralized
                things[key].append(con)
        # get description, build string
        string = "|c%s|n\n" % self.get_display_name(looker)
        desc = self.get_description(looker)
        if desc:
            string += "%s" % desc
        if exits:
            string += "\n|wExits:|n " + list_to_string(exits)
        if users or things:
            # handle pluralization of things (never pluralize users)
            thing_strings = []
            for key, itemlist in sorted(things.items()):
                nitem = len(itemlist)
                if nitem == 1:
                    key, _ = itemlist[0].get_numbered_name(nitem, looker, key=key)
                else:
                    key = [item.get_numbered_name(nitem, looker, key=key)[1] for item in itemlist][0]
                thing_strings.append(key)

            string += "\n|wYou see:|n " + list_to_string(users + thing_strings)

        return string

    def at_look(self, target, **kwargs):
        """
        Called when this object performs a look. It allows to
        customize just what this means. It will not itself
        send any data.

        Args:
            target (Object): The target being looked at. This is
                commonly an object or the current location. It will
                be checked for the "view" type access.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call. This will be passed into
                return_appearance, get_display_name and at_desc but is not used
                by default.

        Returns:
            lookstring (str): A ready-processed look string
                potentially ready to return to the looker.

        """
        if not target.access(self, "view"):
            try:
                return "Could not view '%s'." % target.get_display_name(self, **kwargs)
            except AttributeError:
                return "Could not view '%s'." % target.key

        description = target.return_appearance(self, **kwargs)

        # the target's at_desc() method.
        # this must be the last reference to target so it may delete itself when acted on.
        target.at_desc(looker=self, **kwargs)

        return description

    def at_desc(self, looker=None, **kwargs):
        """
        This is called whenever someone looks at this object.

        Args:
            looker (Object, optional): The object requesting the description.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        """
        pass

    def at_before_get(self, getter, **kwargs):
        """
        Called by the default `get` command before this object has been
        picked up.

        Args:
            getter (Object): The object about to get this object.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        Returns:
            shouldget (bool): If the object should be gotten or not.

        Notes:
            If this method returns False/None, the getting is cancelled
            before it is even started.
        """
        return True

    def at_get(self, getter, **kwargs):
        """
        Called by the default `get` command when this object has been
        picked up.

        Args:
            getter (Object): The object getting this object.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        Notes:
            This hook cannot stop the pickup from happening. Use
            permissions or the at_before_get() hook for that.

        """
        pass

    def at_before_give(self, giver, getter, **kwargs):
        """
        Called by the default `give` command before this object has been
        given.

        Args:
            giver (Object): The object about to give this object.
            getter (Object): The object about to get this object.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        Returns:
            shouldgive (bool): If the object should be given or not.

        Notes:
            If this method returns False/None, the giving is cancelled
            before it is even started.

        """
        return True

    def at_give(self, giver, getter, **kwargs):
        """
        Called by the default `give` command when this object has been
        given.

        Args:
            giver (Object): The object giving this object.
            getter (Object): The object getting this object.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        Notes:
            This hook cannot stop the give from happening. Use
            permissions or the at_before_give() hook for that.

        """
        pass

    def at_before_drop(self, dropper, **kwargs):
        """
        Called by the default `drop` command before this object has been
        dropped.

        Args:
            dropper (Object): The object which will drop this object.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        Returns:
            shoulddrop (bool): If the object should be dropped or not.

        Notes:
            If this method returns False/None, the dropping is cancelled
            before it is even started.

        """
        return True

    def at_drop(self, dropper, **kwargs):
        """
        Called by the default `drop` command when this object has been
        dropped.

        Args:
            dropper (Object): The object which just dropped this object.
            **kwargs (dict): Arbitrary, optional arguments for users
                overriding the call (unused by default).

        Notes:
            This hook cannot stop the drop from happening. Use
            permissions or the at_before_drop() hook for that.

        """
        pass

    def at_before_say(self, message, **kwargs):
        """
        Before the object says something.

        This hook is by default used by the 'say' and 'whisper'
        commands as used by this command it is called before the text
        is said/whispered and can be used to customize the outgoing
        text from the object. Returning `None` aborts the command.

        Args:
            message (str): The suggested say/whisper text spoken by self.
        Kwargs:
            whisper (bool): If True, this is a whisper rather than
                a say. This is sent by the whisper command by default.
                Other verbal commands could use this hook in similar
                ways.
            receivers (Object or iterable): If set, this is the target or targets for the say/whisper.

        Returns:
            message (str): The (possibly modified) text to be spoken.

        """
        return message

    def at_say(self, message, msg_self=None, msg_location=None,
               receivers=None, msg_receivers=None, **kwargs):
        """
        Display the actual say (or whisper) of self.

        This hook should display the actual say/whisper of the object in its
        location.  It should both alert the object (self) and its
        location that some text is spoken.  The overriding of messages or
        `mapping` allows for simple customization of the hook without
        re-writing it completely.

        Args:
            message (str): The message to convey.
            msg_self (bool or str, optional): If boolean True, echo `message` to self. If a string,
                return that message. If False or unset, don't echo to self.
            msg_location (str, optional): The message to echo to self's location.
            receivers (Object or iterable, optional): An eventual receiver or receivers of the message
                (by default only used by whispers).
            msg_receivers(str): Specific message to pass to the receiver(s). This will parsed
                with the {receiver} placeholder replaced with the given receiver.
        Kwargs:
            whisper (bool): If this is a whisper rather than a say. Kwargs
                can be used by other verbal commands in a similar way.
            mapping (dict): Pass an additional mapping to the message.

        Notes:


            Messages can contain {} markers. These are substituted against the values
            passed in the `mapping` argument.

                msg_self = 'You say: "{speech}"'
                msg_location = '{object} says: "{speech}"'
                msg_receivers = '{object} whispers: "{speech}"'

            Supported markers by default:
                {self}: text to self-reference with (default 'You')
                {speech}: the text spoken/whispered by self.
                {object}: the object speaking.
                {receiver}: replaced with a single receiver only for strings meant for a specific
                    receiver (otherwise 'None').
                {all_receivers}: comma-separated list of all receivers,
                                 if more than one, otherwise same as receiver
                {location}: the location where object is.

        """
        msg_type = 'say'
        if kwargs.get("whisper", False):
            # whisper mode
            msg_type = 'whisper'
            msg_self = '{self} whisper to {all_receivers}, "{speech}"' if msg_self is True else msg_self
            msg_receivers = '{object} whispers: "{speech}"'
            msg_receivers = msg_receivers or '{object} whispers: "{speech}"'
            msg_location = None
        else:
            msg_self = '{self} say, "{speech}"' if msg_self is True else msg_self
            msg_location = msg_location or '{object} says, "{speech}"'
            msg_receivers = msg_receivers or message

        custom_mapping = kwargs.get('mapping', {})
        receivers = make_iter(receivers) if receivers else None
        location = self.location

        if msg_self:
            self_mapping = {"self": "You",
                            "object": self.get_display_name(self),
                            "location": location.get_display_name(self) if location else None,
                            "receiver": None,
                            "all_receivers": ", ".join(
                                recv.get_display_name(self)
                                for recv in receivers) if receivers else None,
                            "speech": message}
            self_mapping.update(custom_mapping)
            self.msg(text=(msg_self.format(**self_mapping), {"type": msg_type}), from_obj=self)

        if receivers and msg_receivers:
            receiver_mapping = {"self": "You",
                                "object": None,
                                "location": None,
                                "receiver": None,
                                "all_receivers": None,
                                "speech": message}
            for receiver in make_iter(receivers):
                individual_mapping = {"object": self.get_display_name(receiver),
                                      "location": location.get_display_name(receiver),
                                      "receiver": receiver.get_display_name(receiver),
                                      "all_receivers": ", ".join(
                                            recv.get_display_name(recv)
                                            for recv in receivers) if receivers else None}
                receiver_mapping.update(individual_mapping)
                receiver_mapping.update(custom_mapping)
                receiver.msg(text=(msg_receivers.format(**receiver_mapping),
                             {"type": msg_type}), from_obj=self)

        if self.location and msg_location:
            location_mapping = {"self": "You",
                                "object": self,
                                "location": location,
                                "all_receivers": ", ".join(str(recv) for recv in receivers) if receivers else None,
                                "receiver": None,
                                "speech": message}
            location_mapping.update(custom_mapping)
            exclude = []
            if msg_self:
                exclude.append(self)
            if receivers:
                exclude.extend(receivers)
            self.location.msg_contents(text=(msg_location, {"type": msg_type}),
                                       from_obj=self,
                                       exclude=exclude,
                                       mapping=location_mapping)


class AbstractMapEntity(*MAPENT_MIXINS, AthanorGameEntity):
    """
    A sub-class of AthanorGameEntity that's specialized for being chunks of the map.
    """

    def __init__(self, unique_key, handler, data):
        AthanorGameEntity.__init__(self, data)
        self.unique_key = unique_key
        self.handler = handler
        self.instance = handler.owner
