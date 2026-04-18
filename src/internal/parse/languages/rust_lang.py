from typing import List, Tuple

from src.internal.parse.base import CallSite, ImportRef, LanguageAdapter, Symbol


class RustAdapter(LanguageAdapter):
    language_name = "rust"
    file_extensions = (".rs",)
    function_node_types = ("function_item",)
    class_node_types = ("struct_item", "enum_item", "impl_item")
    import_node_types = ("use_declaration",)
    call_node_types = ("call_expression", "method_call_expression")

    _CLASS_KIND = {
        "struct_item": "class",
        "enum_item": "class",
        "impl_item": "class",
    }

    def extract_index_data(
        self, tree, source_lines: List[str], filepath: str
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
                sym = self._symbol_from_function_item(node, source_lines, filepath)
                if sym is not None:
                    symbols.append(sym)
            elif t in self.class_node_types:
                sym = self._symbol_from_class_like(node, source_lines, filepath)
                if sym is not None:
                    symbols.append(sym)
            elif t in self.import_node_types:
                line = source_lines[node.start_point[0]].strip() if source_lines else ""
                imports.append(
                    ImportRef(
                        symbol_name=node.text.decode(), file=filepath, import_line=line
                    )
                )
            elif t in self.call_node_types:
                site = self._call_site_from_node(node, source_lines, filepath)
                if site is not None:
                    calls.append(site)
        return symbols, calls, imports

    def _symbol_from_function_item(
        self, node, source_lines: List[str], filepath: str
    ) -> Symbol | None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
        return Symbol(
            name=name_node.text.decode(),
            kind="function",
            file=filepath,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=sig,
            language="rust",
        )

    def _symbol_from_class_like(
        self, node, source_lines: List[str], filepath: str
    ) -> Symbol | None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
        return Symbol(
            name=name_node.text.decode(),
            kind=self._CLASS_KIND.get(node.type, "class"),
            file=filepath,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=sig,
            language="rust",
        )

    def _call_site_from_node(
        self, node, source_lines: List[str], filepath: str
    ) -> CallSite | None:
        if node.type == "call_expression":
            fn_node = node.child_by_field_name("function")
        else:
            fn_node = node.child_by_field_name("method")
        if not fn_node:
            return None
        full_name = fn_node.text.decode()
        name = full_name.split("::")[-1].split(".")[-1]
        line_idx = node.start_point[0]
        context = source_lines[line_idx].rstrip() if source_lines else ""
        return CallSite(
            symbol_name=name,
            caller_file=filepath,
            line=line_idx + 1,
            context=context,
            full_name=full_name,
        )

    def is_test_file(self, filepath: str) -> bool:
        parts = filepath.replace("\\", "/").split("/")
        return "tests" in parts
