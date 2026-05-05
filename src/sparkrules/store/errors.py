class StoreUnavailableError(RuntimeError):
    """Raised when a persistent store backend cannot read or write (e.g. corrupt file, DB down)."""
