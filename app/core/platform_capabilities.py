"""Optional OS capabilities; importing this module never loads a BLE backend."""
import sys
import importlib.util


BLE_UNAVAILABLE = 'Bluetooth LE is not supported on this Windows version.'
COPERNICUS_UNAVAILABLE = 'Copernicus Marine data is unavailable in the Windows 7/8 compatibility build.'


def windows_version():
    if sys.platform != 'win32':
        return None
    version = sys.getwindowsversion()
    return tuple(getattr(version, 'platform_version', (version.major, version.minor, version.build)))


def native_ble_available():
    version = windows_version()
    return version is None or version >= (10, 0, 16299)


def copernicus_available():
    loaded = sys.modules.get('copernicusmarine')
    if loaded is not None:
        return callable(getattr(loaded, 'open_dataset', None))
    return importlib.util.find_spec('copernicusmarine') is not None
