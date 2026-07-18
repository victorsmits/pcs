class ProviderError(Exception):
    """Base métier des erreurs provider."""


class ProviderCapabilityNotSupported(ProviderError):
    """La capacité demandée n'est pas déclarée par le provider."""


class ProviderDisabled(ProviderError):
    """Le provider est désactivé en configuration ou en base."""


class ProviderRateLimited(ProviderError):
    def __init__(self, retry_after_seconds: int | None = None):
        self.retry_after_seconds = retry_after_seconds
        super().__init__('provider rate limited')


class ProviderCircuitOpen(ProviderError):
    def __init__(self, retry_after_seconds: int | None = None):
        self.retry_after_seconds = retry_after_seconds
        super().__init__('provider circuit open')


class ProviderForbidden(ProviderError):
    """Un 403 doit échouer proprement, sans contournement ni impersonation."""


class ProviderInvalidPayload(ProviderError):
    """Le payload reçu ne respecte pas le contrat normalisé."""
