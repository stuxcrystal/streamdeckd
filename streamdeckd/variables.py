from typing import cast, Mapping, Any, Dict
from collections import UserDict, ChainMap


class _EmptyMap(UserDict):

    def __init__(self):
        super().__init__({})


class Variables(UserDict):

    def __init__(self):
        super().__init__()
        self.maps = []
        self.add_map(_EmptyMap())

    def add_map(self, map: Mapping[Any, Any]):
        self.maps.append(map)
        self.data = cast(Dict[Any, Any], ChainMap(*reversed(self.maps)))
    
    def remove_map(self, map: Mapping[Any, Any]):
        while map in self.maps:
            self.maps.remove(map)
        self.data = cast(Dict[Any, Any], ChainMap(*reversed(self.maps)))

    def make_child(self) -> 'Variables':
        result = Variables()
        result.add_map(self)
        return result

    def format(self, string: str) -> str:
        return string.format(**self)