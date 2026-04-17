import os
from typing import Optional, TypedDict

from src.internal.parse.base import LanguageAdapter
from src.internal.parse.languages.go_lang import GoAdapter
from src.internal.parse.languages.javascript_lang import JavaScriptAdapter
from src.internal.parse.languages.python_lang import PythonAdapter
from src.internal.parse.languages.rust_lang import RustAdapter


class _AdapterSpec(TypedDict):
    adapter: type[LanguageAdapter]
    extensions: tuple[str, ...]


class AdapterFactory:
    adapters: dict[str, _AdapterSpec] = {
        "python": {
            "adapter": PythonAdapter,
            "extensions": PythonAdapter.file_extensions,
        },
        "javascript": {
            "adapter": JavaScriptAdapter,
            "extensions": JavaScriptAdapter.file_extensions,
        },
        "rust": {
            "adapter": RustAdapter,
            "extensions": RustAdapter.file_extensions,
        },
        "go": {
            "adapter": GoAdapter,
            "extensions": GoAdapter.file_extensions,
        },
    }

    @staticmethod
    def get_adapter(filepath: str) -> Optional[LanguageAdapter]:
        ext = os.path.splitext(filepath)[1].lower()
        for cfg in AdapterFactory.adapters.values():
            if ext in cfg["extensions"]:
                return cfg["adapter"]()
        return None
