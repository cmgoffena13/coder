from dataclasses import dataclass
from typing import List, cast

from tree_sitter_language_pack import SupportedLanguage, get_parser


@dataclass
class Symbol:
    name: str
    kind: str
    file: str
    start_line: int
    end_line: int
    signature: str
    language: str = ""


@dataclass
class CallSite:
    symbol_name: str
    caller_file: str
    line: int
    context: str
    full_name: str = ""


@dataclass
class ImportRef:
    symbol_name: str
    file: str
    import_line: str


class LanguageAdapter:
    language_name: str = ""
    file_extensions: tuple = ()
    function_node_types: tuple = ()
    class_node_types: tuple = ()
    import_node_types: tuple = ()
    call_node_types: tuple = ()

    def _get_parser(self):
        # Subclasses set ``language_name`` to a supported grammar id.
        return get_parser(cast(SupportedLanguage, self.language_name))

    def parse(self, source: bytes):
        return self._get_parser().parse(source)

    def parse_file(self, source: bytes, filepath: str):
        """Subclasses may choose grammar by ``filepath``; default uses ``parse``."""
        return self.parse(source)

    def _node_text(self, node, source_lines: List[str]) -> str:
        return source_lines[node.start_point[0]] if source_lines else ""

    def _node_lines(self, node, source_lines: List[str]) -> List[str]:
        return source_lines[node.start_point[0] : node.end_point[0] + 1]

    def extract_symbols(
        self, tree, source_lines: List[str], filepath: str
    ) -> List[Symbol]:
        symbols: List[Symbol] = []
        symbols.extend(self.extract_functions(tree, source_lines, filepath))
        symbols.extend(self.extract_classes(tree, source_lines, filepath))
        return symbols

    def extract_functions(
        self, tree, source_lines: List[str], filepath: str
    ) -> List[Symbol]:
        raise NotImplementedError

    def extract_classes(
        self, tree, source_lines: List[str], filepath: str
    ) -> List[Symbol]:
        raise NotImplementedError

    def extract_imports(
        self, tree, source_lines: List[str], filepath: str
    ) -> List[ImportRef]:
        raise NotImplementedError

    def extract_calls(
        self, tree, source_lines: List[str], filepath: str
    ) -> List[CallSite]:
        raise NotImplementedError

    def is_test_file(self, filepath: str) -> bool:
        return False

    def _walk(self, node, node_types: tuple):
        if node.type in node_types:
            yield node
        for child in node.children:
            yield from self._walk(child, node_types)
