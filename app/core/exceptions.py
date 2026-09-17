class DatabaseUnavailableError(RuntimeError):
    """Raised by services when the database cannot be reached.

    Mapped to HTTP 503 by an exception handler in app.main.
    The original error is logged server-side, never sent to clients.
    """
