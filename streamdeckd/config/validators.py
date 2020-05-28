from typing import Sequence, Optional
from functools import wraps


def validate(name: str, args: Sequence[str], block: Optional[Sequence[dict]], *, min_args: Optional[int]=None, max_args: Optional[int]=None, with_block: Optional[bool]=None):
    if ((min_args is None) or (len(args) < min_args)) and ((max_args is None) or (len(args) > max_args)):
        if min_args == max_args:
            raise ValueError(f"{name}: Expected {min_args} arguments, got {len(args)}")
        else:
            raise ValueError(f"{name}: Expected between {min_args} and {max_args} arguments, got {len(args)}")
    
    if with_block is not None:
        if not with_block and block is not None:
            raise ValueError(f"{name}: Directive does not accept a block")
        elif with_block and block is None:
            raise ValueError(f"{name}: Directive does not requires a block")


def validated(*, requires_self=True, **kwargs):
    def _decorator(func):
        @wraps(func)
        def _wrapped(self, args: Sequence[str], block: Optional[Sequence[dict]]):
            validate(func.__name__[3:], args, block, **kwargs)
            if requires_self:
                return func(self, args, block)
            else:
                return func(args, block)

        if not requires_self:
            _wrapped = _wrapped.__get__(1)

        return _wrapped
    return _decorator
        