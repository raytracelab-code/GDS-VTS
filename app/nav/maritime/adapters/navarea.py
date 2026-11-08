"""No undocumented HTML/PDF scraping or inferred warning coordinates."""
from .base import SourceAdapter
from .provider_common import ProviderUnavailable


class Navarea8Adapter(SourceAdapter):
    def __init__(self,config):self.config=config
    def fetch(self,area):raise ProviderUnavailable('NO_STABLE_MACHINE_API')
