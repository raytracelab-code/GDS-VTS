"""LAN adapter selection using Qt's existing cross-version network module."""
from dataclasses import dataclass
from importlib import import_module
from app.qt import API
from .photo_server import is_lan_address


@dataclass(frozen=True)
class LanAddress:
    address: str
    name: str
    virtual: bool = False

    @property
    def label(self):
        return '%s — %s' % (self.address,self.name)


def lan_addresses():
    network = import_module(API+'.QtNetwork')
    flags = network.QNetworkInterface.InterfaceFlag
    candidates = []
    for interface in network.QNetworkInterface.allInterfaces():
        state = interface.flags()
        if not state & flags.IsUp or not state & flags.IsRunning or state & flags.IsLoopBack:
            continue
        name = interface.humanReadableName() or interface.name()
        virtual = any(marker in (name+' '+interface.name()).casefold() for marker in
                      ('virtual','vmware','vbox','vethernet','hyper-v','docker','wsl','vpn','wireguard','tailscale','zerotier','tap-','tun'))
        for entry in interface.addressEntries():
            address = entry.ip().toString()
            if is_lan_address(address) and address not in [candidate.address for candidate in candidates]:
                candidates.append(LanAddress(address,name,virtual))
    return sorted(candidates,key=lambda item:(item.virtual,item.name.casefold(),item.address))
