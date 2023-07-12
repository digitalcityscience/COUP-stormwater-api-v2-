class StormwaterApiError(Exception):
    """Base class for all Stormwater API errors."""

    ...


class AuthError(Exception):
    def __init__(self):
        super().__init__()
        self.message = ""
