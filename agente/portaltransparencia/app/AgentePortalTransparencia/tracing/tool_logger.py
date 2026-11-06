import json
import logging

from strands.hooks import HookProvider, HookRegistry, AfterToolCallEvent

log = logging.getLogger(__name__)

if not log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False

class LogTools(HookProvider):
    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(AfterToolCallEvent, self.depois_da_tool)

    def depois_da_tool(self, event: AfterToolCallEvent) -> None:
        nome = event.tool_use["name"]
        params = event.tool_use["input"]
        status = event.result["status"]
        log.info(f"TOOL {nome} {json.dumps(params, ensure_ascii=False)} -> {status}") 