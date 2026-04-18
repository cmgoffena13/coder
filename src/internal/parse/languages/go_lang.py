from pathlib import Path
from typing import List, Tuple

from src.internal.parse.base import CallSite, ImportRef, LanguageAdapter, Symbol


class GoAdapter(LanguageAdapter):
    language_name = "go"
    file_extensions = (".go",)
    function_node_types = ("function_declaration", "method_declaration")
    class_node_types = ("type_declaration",)
    import_node_types = ("import_declaration",)
    call_node_types = ("call_expression",)

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
                for spec in self._walk(node, frozenset(("type_spec",))):
                    sym = self._symbol_from_type_spec(
                        spec, node, source_lines, filepath
                    )
                    if sym is not None:
                        symbols.append(sym)
            elif t in self.import_node_types:
                imports.extend(
                    self._import_refs_from_declaration(node, source_lines, filepath)
                )
            elif t in self.call_node_types:
                site = self._call_site_from_node(node, source_lines, filepath)
                if site is not None:
                    calls.append(site)
        return symbols, calls, imports

    def _symbol_from_function_node(
        self, node, source_lines: List[str], filepath: Path
    ) -> Symbol | None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        kind = "method" if node.type == "method_declaration" else "function"
        sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
        return Symbol(
            name=name_node.text.decode(),
            kind=kind,
            file=str(filepath),
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=sig,
            language="go",
        )

    def _symbol_from_type_spec(
        self, spec, type_decl_node, source_lines: List[str], filepath: Path
    ) -> Symbol | None:
        name_node = spec.child_by_field_name("name")
        if not name_node:
            return None
        sig = (
            source_lines[type_decl_node.start_point[0]].rstrip() if source_lines else ""
        )
        return Symbol(
            name=name_node.text.decode(),
            kind="class",
            file=str(filepath),
            start_line=type_decl_node.start_point[0] + 1,
            end_line=type_decl_node.end_point[0] + 1,
            signature=sig,
            language="go",
        )

    def _import_refs_from_declaration(
        self, node, source_lines: List[str], filepath: Path
    ) -> List[ImportRef]:
        refs: List[ImportRef] = []
        line = source_lines[node.start_point[0]].strip() if source_lines else ""
        for child in self._walk(node, frozenset(("import_spec",))):
            path_node = child.child_by_field_name("path")
            if path_node:
                pkg = path_node.text.decode().strip('"').split("/")[-1]
                refs.append(
                    ImportRef(symbol_name=pkg, file=str(filepath), import_line=line)
                )
        return refs

    def _call_site_from_node(
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
        return filepath.name.endswith("_test.go")
