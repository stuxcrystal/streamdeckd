import weakref
from typing import Optional, Dict, Any, Set, MutableMapping, Callable, Type, Sequence


_UNSET = object()
_STATE_VARIABLES: MutableMapping[Any, Any] = weakref.WeakKeyDictionary()


class StateVariable(object):

    def __init__(self, default=_UNSET):
        super().__init__()
        self.state = weakref.WeakKeyDictionary()
        self.default = default
        self._changed = None
        self.name = None

    def changed(self, cb):
        self._changed = cb
        return self

    def _convert(self, data: str) -> Any:
        return data

    def __set__(self, owner, data):
        old = self.state.get(owner, _UNSET)
        new  = self._convert(data)
        if old == new:
            return

        self.state[owner] = new
        if self._changed is not None:
            self._changed(owner, old, new)

    def __get__(self, instance, owner=None):
        while isinstance(instance, State):
            if instance in self.state:
                return self.state[instance]
            instance = instance.parent
        if self.default is _UNSET:
            raise AttributeError()
        else:
            return self.default

    def __delete__(self, instance):
        self.state.pop(instance, None)

    def __set_name__(self, owner, name):
        self.name = name
        _STATE_VARIABLES.setdefault(owner, []).append(name)

    @classmethod
    def from_parser(cls, func: Callable[[str], Any]) -> Type['StateVariable']:
        return type(
            f"{func.__name__}StateVariable",
            (cls,),
            {"_convert": lambda self, data: func(data)}
        )

    @classmethod
    def with_parser(cls, func: Callable[[str], Any], default=_UNSET) -> 'StateVariable':
        return cls.from_parser(func)(default)


class State(object):

    def __init__(self, parent: Optional['State']):
        super().__init__()
        self.parent = parent

    def apply(self, settings: Dict[str, Any], unseen: Optional[Set[str]]=None, exclude_classes: Sequence[Type['State']]=()):
        if unseen is None:
            unseen = set(settings.keys())

        for cls in self.__class__.mro():
            if cls not in _STATE_VARIABLES:
                continue
            if cls in exclude_classes:
                continue

            vars_here = unseen & set(_STATE_VARIABLES[cls])
            for variable in vars_here:
                setattr(self, variable, settings[variable])
            
            unseen -= vars_here

        if self.parent is not None:
            self.parent.apply(settings, unseen, exclude_classes=exclude_classes)
