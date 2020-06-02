import json
import asyncio
from typing import Type, Sequence, Optional, Any

import aiohttp
from jsonpath_ng import parse as parse_jsonpath

from streamdeckd.application import Streamdeckd

from streamdeckd.config.base import Context
from streamdeckd.config.validators import validated
from streamdeckd.config.application import ApplicationContext
from streamdeckd.config.action import ActionableContext, ActionContext


USER_VARS = {}


class Parser(Context):

    def read_directive(self, args: Sequence[str], block: Optional[Sequence[dict]]):
        self.apply_block(block)

    async def parse(self, response: aiohttp.ClientResponse) -> Any:
        pass


PARSERS={}
def register_parser(name, c=None):
    def _decorator(cls):
        PARSERS[name] = cls
        return cls
    if c is not None:
        return _decorator(c)
    return _decorator


@register_parser("ignore")
class IgnoreParser(Parser):

    async def parse(self, response: aiohttp.ClientResponse) -> str:
        return ""


@register_parser("text")
class TextParser(Parser):

    def __init__(self):
        self.encoding = None
        self.encoding_errors = "strict"

    @validated(min_args=0, max_args=0)    
    def read_directive(self, args: Sequence[str], block: Optional[Sequence[dict]]):
        if block is None:
            block = []
        super().read_directive(args, block)

    @validated(min_args=1, max_args=2, with_block=False)
    def on_encoding(self, args: Sequence[str], block: None):
        self.encoding = args[0]
        if len(args) == 2:
            self.encoding_erros = args[1]

    async def parse(self, response: aiohttp.ClientResponse) -> str:
        try:
            return await response.text(encoding=self.encoding, errors=self.encoding_errors)
        except UnicodeDecodeError:
            return ""


@register_parser("json")
class JSONParser(Parser):

    def __init__(self):
        self.encoding = None
        self.encoding_errors = "strict"
        self.path = None

    @validated(min_args=0, max_args=1)
    def read_directive(self, args: Sequence[str], block: Optional[Sequence[dict]]):
        if block is None:
            block = []
        if len(args) == 1:
            self.path = parse(args[0])
        super().read_directive(args, block)

    @validated(min_args=1, max_args=2, with_block=False)
    def on_encoding(self, args: Sequence[str], block: None):
        self.encoding = args[0]
        if len(args) == 2:
            self.encoding_erros = args[1]
        
    async def parse(self, response: aiohttp.ClientResponse) -> Any:
        try:
            json = await response.json(encoding=self.encoding)
        except UnicodeDecodeError:
            return ""

        if self.path is not None:
            return self.path.find(json)
        else:
            return json


class RequestContext(ActionableContext):

    def __init__(self, request_type: str, uri: str):
        self.uri = uri
        self.request_type = request_type
        self.headers = {}
        self.body = ""
        self.encoding = "utf-8"
        self.parser = IgnoreParser()
        self.variable = None

    @validated(min_args=1)
    def on_parser(self, args, block):
        parser = PARSERS[args[0]]()
        rest = args[1:]
        parser.read_directive(rest, block)

        self.parser = parser

    @validated(min_args=1, max_args=1, with_block=False)
    def on_encoding(self, args, block):
        self.encoding = args[0]

    @validated(min_args=2, max_args=2, with_block=False)
    def on_header(self, args, block):
        hdr_name, hdr_value = args
        self.headers[hdr_name] = hdr_value

    @validated(min_args=1, max_args=1, with_block=False)
    def on_body(self, args, block):
        self.body = ""

    @validated(min_args=1, max_args=1, with_block=False)
    def on_variable(self, args, block):
        USER_VARS[args[0]] = ""
        self.variable = args[0]

    async def apply_actions(self, app, __):
        uri = app.variables.format(self.uri)
        body = app.variables.format(self.body)

        hdrs = {}
        for k, v in self.headers.items():
            hdrs[app.variables.format(k)] = app.variables.format(v)

        async with aiohttp.request(self.request_type, uri, data=body.encode(self.encoding), headers=hdrs) as response:
            result = await self.parser.parse(response)
            if self.variable is not None:
                USER_VARS[self.variable] = result


class HttpActionContext(ActionContext):

    @validated(min_args=2, max_args=2)
    def on_http(self, args, block):
        ctx = RequestContext(args[0], args[1])
        if block is not None:
            ctx.apply_block(block)
        self.actions.append(ctx)

def load(app: Streamdeckd, ctx: ApplicationContext):
    ActionContext.register(HttpActionContext)

async def start(app: Streamdeckd):
    app.variables.add_map(USER_VARS)

async def stop(app: Streamdeckd):
    app.variables.remove_map(USER_VARS)
    await asyncio.sleep(0.25)
