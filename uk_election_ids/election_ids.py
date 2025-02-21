from datetime import datetime
from .datapackage import ELECTION_TYPES
from .parser import DataPackageParser
from .slugger import slugify


parser = DataPackageParser(ELECTION_TYPES)
RULES = parser.build_rules()
CONTEST_TYPES = ("by", "by election", "by-election", "election")

def parse(identifier):
    """Parse an identifier
    Args:
        identifier (str): String identifier we want to validate
    Returns:
        IDBuilder
    """
    if not isinstance(identifier, str):
        return False

    id_parts = identifier.split(".")

    # must have at least an election type and a date
    if len(id_parts) < 2:
        return False

    # check for invalid characters
    for part in id_parts:
        if slugify(part) != str(part):
            return False

    election_type = id_parts.pop(0)
    date = id_parts.pop(-1)

    try:
        builder = IdBuilder(election_type, date)
        return builder
    except (ValueError, NotImplementedError):
        return False

def validate(identifier):
    """Validate an identifier

    Args:
        identifier (str): String identifier we want to validate

    Returns:
        bool
    """
    if not isinstance(identifier, str):
        return False

    id_parts = identifier.split(".")

    # must have at least an election type and a date
    if len(id_parts) < 2:
        return False

    # check for invalid characters
    for part in id_parts:
        if slugify(part) != str(part):
            return False

    election_type = id_parts.pop(0)
    date = id_parts.pop(-1)

    try:
        builder = IdBuilder(election_type, date)
    except (ValueError, NotImplementedError):
        return False
    if len(id_parts) == 0:
        return True

    try:
        # use the builder object to validate the remaining parts,
        # popping as we go
        if id_parts[-1] == "by":
            contest_type = id_parts.pop(-1)
            builder = builder.with_contest_type("by")
        if builder.spec.subtypes:
            subtype = id_parts.pop(0)
            builder = builder.with_subtype(subtype)
        if id_parts and builder.spec.can_have_orgs:
            org = id_parts.pop(0)
            builder = builder.with_organisation(org)
        if id_parts and builder.spec.can_have_divs:
            div = id_parts.pop(0)
            builder = builder.with_division(div)
    except ValueError:
        return False

    # if we've got anything left over, that's wrong
    if len(id_parts) > 0:
        return False

    return True


class IdBuilder:

    """
    Builder object for creating
    `Democracy Club Election Identifiers <https://elections.democracyclub.org.uk/reference_definition>`_.
    """

    def __init__(self, election_type, date):
        """Constructor

        Args:
            election_type (str): May be one of
                ``['europarl', 'gla', 'local', 'mayor', 'naw', 'nia', 'parl', 'pcc', 'sp', 'senedd', 'ref']``
            date (date|str): May be either a python date object,
                or a string in 'Y-m-d' format.
                ``myid = IdBuilder('local', date(2018, 5, 3))`` and
                ``myid = IdBuilder('local', '2018-05-03'))``
                are functionally equivalent invocations.

        Returns:
            IdBuilder
        """
        self._validate_election_type(election_type)
        self.election_type = election_type
        self.spec = RULES[self.election_type]
        self.date = self._format_date(date)
        self.subtype = None
        self.organisation = None
        self.division = None
        self.contest_type = None

    def _format_date(self, date):
        if isinstance(date, str):
            # if we've been given a string, validate it
            # by converting to a datetime and back again
            return datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")

        return date.strftime("%Y-%m-%d")

    @property
    def _can_have_divs(self):
        if isinstance(self.spec.can_have_divs, (bool,)):
            return self.spec.can_have_divs
        else:
            return self.spec.can_have_divs[self.subtype]

    def with_subtype(self, subtype):
        """Add a subtype segment

        Args:
            subtype (str): May be one of ``['a', 'c', 'r']``. See the
                `Reference Definition <https://elections.democracyclub.org.uk/reference_definition>`_.
                for valid election type/subtype combinations.

        Returns:
            IdBuilder

        Raises:
            ValueError
        """
        self._validate_subtype(subtype)
        self.subtype = subtype
        return self

    def with_organisation(self, organisation):
        """Add an organisation segment.

        Args:
            organisation (str): Official name of an administrative body
                holding an election.

        Returns:
            IdBuilder

        Raises:
            ValueError
        """
        if organisation is None:
            organisation = ""
        organisation = slugify(organisation)
        self._validate_organisation(organisation)
        self.organisation = organisation
        return self

    def with_division(self, division):
        """Add a division segment

        Args:
            division (str): Official name of an electoral division.

        Returns:
            IdBuilder

        Raises:
            ValueError
        """
        if division is None:
            division = ""
        division = slugify(division)
        self._validate_division(division)
        self.division = division
        return self

    def with_contest_type(self, contest_type):
        """Add a contest_type segment

        Args:
            contest_type (str): Invoke with ``contest_type='by'`` or
                ``contest_type='by-election'`` to add a 'by' segment to the
                ballot_id. Invoking with ``contest_type='election'`` is valid
                syntax but has no effect.

        Returns:
            IdBuilder

        Raises:
            ValueError
        """
        self._validate_contest_type(contest_type)
        if contest_type.lower() in ("by", "by election", "by-election"):
            if self.election_type == "ref":
                raise ValueError(
                    "election_type %s may not have a by-election" % (self.election_type)
                )
            self.contest_type = "by"
        return self

    def _validate_election_type(self, election_type):
        if election_type not in ELECTION_TYPES:
            raise ValueError(
                "Allowed values for election_type are %s"
                % (str(list(ELECTION_TYPES.keys())))
            )
        return True

    def _validate_subtype(self, subtype):
        if isinstance(self.spec.subtypes, tuple) and subtype not in self.spec.subtypes:
            raise ValueError(
                "Allowed values for subtype are %s" % (str(self.spec.subtypes))
            )
        if not self.spec.subtypes and subtype:
            raise ValueError(
                "election_type %s may not have a subtype" % (self.election_type)
            )
        return True

    def _validate_organisation(self, organisation):
        if not self.spec.can_have_orgs and organisation:
            raise ValueError(
                "election_type %s may not have an organisation" % (self.election_type)
            )
        return True

    def _validate_division(self, division):
        try:
            can_have_divs = self._can_have_divs
        except KeyError:
            raise ValueError(
                "election_type %s must have a valid subtype before setting a division"
                % (self.election_type)
            )
        if not can_have_divs and division:
            raise ValueError(
                "election_type %s may not have a division" % (self.election_type)
            )
        return True

    def _validate_contest_type(self, contest_type):
        if not contest_type:
            return True
        if not contest_type.lower() in CONTEST_TYPES:
            raise ValueError(
                "Allowed values for contest_type are %s" % (str(list(CONTEST_TYPES)))
            )
        return True

    def _validate(self):
        # validation checks necessary to create any id
        self._validate_election_type(self.election_type)
        self._validate_organisation(self.organisation)
        if (
            self.spec.can_have_orgs
            and self._can_have_divs
            and not self.organisation
            and self.division
        ):
            raise ValueError(
                "election_type %s must have an organisation in order to have a division"
                % (self.election_type)
            )
        self._validate_contest_type(self.contest_type)
        return True

    @property
    def election_group_id(self):
        """
        str: Election Group ID
        """
        self._validate()
        # there are no additional validation checks for the top-level group id
        parts = []
        parts.append(self.election_type)
        parts.append(self.date)
        return ".".join(parts)

    def _validate_for_subtype_group_id(self):
        if not isinstance(self.spec.subtypes, tuple):
            raise ValueError(
                "Can't create subtype id for election_type %s" % (self.election_type)
            )
        if isinstance(self.spec.subtypes, tuple) and not self.subtype:
            raise ValueError(
                "Subtype must be specified for election_type %s" % (self.election_type)
            )
        self._validate_subtype(self.subtype)
        return True

    @property
    def subtype_group_id(self):
        """
        str: Subtype Group ID
        """
        self._validate()
        self._validate_for_subtype_group_id()

        parts = []
        parts.append(self.election_type)
        parts.append(self.subtype)
        parts.append(self.date)
        return ".".join(parts)

    def _validate_for_organisation_group_id(self):
        # validation checks specifically relevant to creating an organisation group id
        if isinstance(self.spec.subtypes, tuple) and not self.subtype:
            raise ValueError(
                "Subtype must be specified for election_type %s" % (self.election_type)
            )
        self._validate_subtype(self.subtype)
        if not self.spec.can_have_orgs:
            raise ValueError(
                "election_type %s can not have an organisation group id"
                % (self.election_type)
            )
        if self.spec.can_have_orgs and not self.organisation:
            raise ValueError(
                "election_type %s must have an organisation in order to create an organisation group id"
                % (self.election_type)
            )
        return True

    @property
    def organisation_group_id(self):
        """
        str: Organisation Group ID
        """
        self._validate()
        self._validate_for_organisation_group_id()

        parts = []
        parts.append(self.election_type)
        if self.subtype:
            parts.append(self.subtype)
        parts.append(self.organisation)
        parts.append(self.date)
        return ".".join(parts)

    def _validate_for_ballot_id(self):
        # validation checks specifically relevant to creating a ballot id
        if isinstance(self.spec.subtypes, tuple) and not self.subtype:
            raise ValueError(
                "Subtype must be specified for election_type %s" % (self.election_type)
            )
        self._validate_subtype(self.subtype)
        if self.spec.can_have_orgs and not self.organisation:
            raise ValueError(
                "election_type %s must have an organisation in order to create a ballot id"
                % (self.election_type)
            )
        if self._can_have_divs and not self.division:
            raise ValueError(
                "election_type %s must have a division in order to create a ballot id"
                % (self.election_type)
            )
        return True

    @property
    def ballot_id(self):
        """
        str: Ballot ID
        """
        self._validate()
        self._validate_division(self.division)
        self._validate_for_ballot_id()

        parts = []
        parts.append(self.election_type)
        if self.subtype:
            parts.append(self.subtype)
        if self.organisation:
            parts.append(self.organisation)
        if self.division:
            parts.append(self.division)
        if self.contest_type:
            parts.append(self.contest_type)
        parts.append(self.date)
        return ".".join(parts)

    @property
    def ids(self):
        """
        list[str]: All applicable IDs
        """
        ids = []

        try:
            ids.append(self.election_group_id)
        except ValueError:
            pass

        if isinstance(self.spec.subtypes, tuple):
            try:
                ids.append(self.subtype_group_id)
            except ValueError:
                pass

        if self.spec.can_have_orgs:
            try:
                ids.append(self.organisation_group_id)
            except ValueError:
                pass

        try:
            if self.ballot_id not in ids:
                ids.append(self.ballot_id)
        except ValueError:
            pass

        return ids

    def __repr__(self):
        return str(self.ids)

    def __eq__(self, other):
        return type(other) == IdBuilder and self.__dict__ == other.__dict__
