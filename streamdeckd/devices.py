from typing import Union, Optional, Sequence, List, Dict
from StreamDeck.DeviceManager import DeviceManager
from StreamDeck.Devices.StreamDeck import StreamDeck


class DeviceSource(object):
    def __init__(self):
        super().__init__()

    def rescan(self) -> Sequence[str]:
        pass

    def get_scanned(self, identifier: str) -> Optional[StreamDeck]:
        pass

    def matches(self, identifier: str, deck: StreamDeck) -> bool:
        pass

    def request(self, user_identifier: str) -> None:
        pass

    def enumerate(self) -> Sequence[StreamDeck]:
        pass


class HardwareDeviceSource(DeviceSource):
    def __init__(self):
        super().__init__()
        self.mgr = DeviceManager()

    def rescan(self) -> Sequence[str]:
        return [d.id().decode("ascii") for d in self.mgr.enumerate()]

    def get_scanned(self, identifier: str) -> Optional[StreamDeck]:
        for dev in self.enumerate():
            if dev.id().decode("ascii") == identifier:
                return dev
        return None

    def matches(self, identifier: str, deck: StreamDeck) -> bool:
        deck.open()
        try:
            return deck.get_serial_number() == identifier
        finally:
            deck.close()

    def request(self, user_ident: str) -> None:
        pass

    def enumerate(self) -> Sequence[StreamDeck]:
        return self.mgr.enumerate()


class DeviceSourceDispatch(DeviceSource):
    def __init__(self, **managers: DeviceSource):
        super().__init__()
        self.managers: Dict[str, DeviceSource] = managers

    def rescan(self) -> Sequence[str]:
        result: List[str] = []
        for name, mgr in self.managers.items():
            result.extend(name + "/" + d for d in mgr.rescan())
        return result

    def get_scanned(self, identifier: str) -> Optional[StreamDeck]:
        if identifier.count("/") != 1:
            return None

        src, identifier = identifier.split("/", 1)
        return self.managers[src].get_scanned(identifier)

    def matches(self, identifier: str, deck: StreamDeck):
        if identifier.count(":") != 1:
            return False

        src, identifier = identifier.split(":", 1)
        return self.managers[src].matches(identifier, deck)

    def request(self, identifier: str):
        if identifier.count(":") != 1:
            return False

        src, identifier = identifier.split(":", 1)
        return self.managers[src].request(identifier)


    def enumerate(self) -> Sequence[StreamDeck]:
        result: List[StreamDeck] = []
        for mgr in self.managers.values():
            result.extend(mgr.enumerate())
        return result


def get_default_source() -> DeviceSource:
    return DeviceSourceDispatch(
        usb=HardwareDeviceSource()
    )