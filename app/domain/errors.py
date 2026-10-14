class DomainError(Exception):
    """Base class for all business-rule violations."""


class InvalidStateTransition(DomainError):
    pass


class InvalidSubmission(DomainError):
    pass