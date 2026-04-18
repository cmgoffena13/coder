from pathlib import Path
from typing import List, Tuple

from src.internal.parse.base import CallSite, ImportRef, LanguageAdapter, Symbol

_FUNCTION_TYPES = (
    "function_declaration",
    "function",
    "arrow_function",
    "method_definition",
    "generator_function_declaration",
    "generator_function",
)

_CLASS_TYPES = ("class_declaration", "class")

_IMPORT_TYPES = ("import_statement",)

_CALL_TYPES = ("call_expression",)


class JavaScriptAdapter(LanguageAdapter):
    language_name = "javascript"
    file_extensions = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")
    function_node_types = _FUNCTION_TYPES
    class_node_types = _CLASS_TYPES
    import_node_types = _IMPORT_TYPES
    call_node_types = _CALL_TYPES

    def _parser_for(self, filepath: Path):
        ext = filepath.suffix.lower()
        lang = "typescript" if ext in (".ts", ".tsx") else "javascript"
        return self._parser_for_language(lang)

    def parse_file(self, source: bytes, filepath: Path):
        return self._parser_for(filepath).parse(source)

    def extract_index_data(
        self, tree, source_lines: List[str], filepath: Path
    ) -> Tuple[List[Symbol], List[CallSite], List[ImportRef]]:
        symbols: List[Symbol] = []
        calls: List[CallSite] = []
        imports: List[ImportRef] = []
        types = frozenset(
            self.function_node_types
            + self.class_node_types
            + self.import_node_types
            + self.call_node_types
        )
        for node in self._walk(tree.root_node, types):
            t = node.type
            if t in self.function_node_types:
                sym = self._symbol_from_function_node(node, source_lines, filepath)
                if sym is not None:
                    symbols.append(sym)
            elif t in self.class_node_types:
                sym = self._symbol_from_class_node(node, source_lines, filepath)
                if sym is not None:
                    symbols.append(sym)
            elif t == "import_statement":
                line = source_lines[node.start_point[0]].strip() if source_lines else ""
                for child in self._walk(
                    node, frozenset(("identifier", "namespace_import"))
                ):
                    imports.append(
                        ImportRef(
                            symbol_name=child.text.decode(),
                            file=str(filepath),
                            import_line=line,
                        )
                    )
            elif t == "call_expression":
                fn = node.child_by_field_name("function")
                if fn and fn.text == b"require":
                    line = (
                        source_lines[node.start_point[0]].strip()
                        if source_lines
                        else ""
                    )
                    imports.append(
                        ImportRef(
                            symbol_name="require",
                            file=str(filepath),
                            import_line=line,
                        )
                    )
                site = self._call_site_from_call_expression(
                    node, source_lines, filepath
                )
                if site is not None:
                    calls.append(site)
        return symbols, calls, imports

    def _symbol_from_function_node(
        self, node, source_lines: List[str], filepath: Path
    ) -> Symbol | None:
        name = self._function_name(node)
        if not name:
            return None
        sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
        kind = "method" if node.type == "method_definition" else "function"
        return Symbol(
            name=name,
            kind=kind,
            file=str(filepath),
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=sig,
            language="javascript",
        )

    def _symbol_from_class_node(
        self, node, source_lines: List[str], filepath: Path
    ) -> Symbol | None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
        return Symbol(
            name=name_node.text.decode(),
            kind="class",
            file=str(filepath),
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=sig,
            language="javascript",
        )

    def _call_site_from_call_expression(
        self, node, source_lines: List[str], filepath: Path
    ) -> CallSite | None:
        fn_node = node.child_by_field_name("function")
        if not fn_node:
            return None
        full_name = fn_node.text.decode()
        name = full_name.split(".")[-1]
        line_idx = node.start_point[0]
        context = source_lines[line_idx].rstrip() if source_lines else ""
        return CallSite(
            symbol_name=name,
            caller_file=str(filepath),
            line=line_idx + 1,
            context=context,
            full_name=full_name,
        )

    def is_test_file(self, filepath: Path) -> bool:
        n = filepath.name
        parts = filepath.parts
        return ".test." in n or ".spec." in n or "__tests__" in parts

    def _function_name(self, node) -> str:
        """Extract function name from various function node shapes."""
        name_node = node.child_by_field_name("name")
        if name_node:
            return name_node.text.decode()
        parent = node.parent
        if parent and parent.type == "variable_declarator":
            id_node = parent.child_by_field_name("name")
            if id_node:
                return id_node.text.decode()
        return ""
