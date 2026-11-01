from .models import ConnectionMode


class Settings:
    connection_mode: ConnectionMode = ConnectionMode.AUTO
