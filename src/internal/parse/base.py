from dataclasses import dataclass
from typing import List, Tuple, cast

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

    def __init__(self) -> None:
        self._cached_parsers: dict[str, object] = {}

    def _parser_for_language(self, lang_id: str):
        """One tree-sitter parser per grammar id on this adapter instance."""
        d = self._cached_parsers
        if lang_id not in d:
            d[lang_id] = get_parser(cast(SupportedLanguage, lang_id))
        return d[lang_id]

    def _get_parser(self):
        if not self.language_name:
            raise ValueError("language_name must be set on LanguageAdapter subclass")
        return self._parser_for_language(self.language_name)

    def parse(self, source: bytes):
        return self._get_parser().parse(source)

    def parse_file(self, source: bytes, filepath: str):
        """Subclasses may choose grammar by ``filepath``; default uses ``parse``."""
        return self.parse(source)

    def extract_index_data(
        self, tree, source_lines: List[str], filepath: str
    ) -> Tuple[List[Symbol], List[CallSite], List[ImportRef]]:
        """
        Single pass over the parse tree: symbols, call sites, and imports.

        Subclasses must implement this; indexing uses ``extract_index_data`` only.
        """
        raise NotImplementedError

    def is_test_file(self, filepath: str) -> bool:
        return False

    def _walk(self, node, types: frozenset):
        """Depth-first; yield nodes whose ``type`` is in ``types``."""
        if node.type in types:
            yield node
        for child in node.children:
            yield from self._walk(child, types)
