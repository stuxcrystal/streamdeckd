from typing import Sequence


class Context:

    def apply_block(self, block: Sequence[dict]):
        for directive in block:
            self.apply_directive(directive["directive"], directive.get("args", []), directive.get("block", None))

    def apply_directive(self, name: str, args: Sequence[str], block: Sequence[dict]):
        getattr(self, f"on_{name}", lambda _, __: self.unknown_directive(name, args, block))(args, block)

    def unknown_directive(self, name: str, args: Sequence[str], block: Sequence[dict]):
        raise ValueError(f"Unknown directive '{name}' with args {args!r}")
