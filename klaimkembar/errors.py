from klaimkembar.models import FieldIssue, ValidationSummary


class Rejection(Exception):
    def __init__(self, status: int, code: str, message: str,
                 details: list[FieldIssue] | None = None, validation: ValidationSummary | None = None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []
        self.validation = validation
        super().__init__(code)
