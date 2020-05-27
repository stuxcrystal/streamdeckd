from typing import Callable, TypeVar, Literal, Union, Optional, Dict, List


_UNSET = object()
T_co = TypeVar("T", covariant=True)


class Registry:

    def __init__(self):
        self.items: Dict[str, T_co] = {}
        self.resolvers: List[Callable[[str], Optional[T]]] = []

    def resolver(self, resolver: Union[Callable[[str], Optional[T_co]], Literal[_UNSET]]=_UNSET) -> Optional[Callable[[str], Optional[T_co]]]:
        def _decorator(func):
            self.resolvers.append(func)
            return func

        if resolver is not _UNSET:
            _decorator(resolver)
            return

        return _decorator

    def register(self, name: str, obj: Union[T_co, Literal[_UNSET]]=_UNSET) -> Union[Callable[[T_co], T_co], T_co]:
        def _decorator(func):
            self.items[name] = func

        if obj is not _UNSET:
            _decorator(obj)
            return obj

        return _decorator

    def __getitem__(self, key: str) -> Optional[T]:
        if key in self.items:
            return self.items[key]
        
        for resolver in self.resolvers:
            resolved = self.resolvers(key)
            if resolved is not None:
                break
        else:
            raise KeyError(key)
        
        self.items[key] = resolved
        return resolved
