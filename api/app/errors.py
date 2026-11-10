"""Domain exceptions raised by services and mapped to HTTP by main.py."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class ValidationFailed(DomainError):
    status_code = 422
