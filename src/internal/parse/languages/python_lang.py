from pathlib import Path
from typing import List, Tuple

from src.internal.parse.base import CallSite, ImportRef, LanguageAdapter, Symbol


class PythonAdapter(LanguageAdapter):
    language_name = "python"
    file_extensions = (".py",)
    function_node_types = ("function_definition",)
    class_node_types = ("class_definition",)
    import_node_types = ("import_statement", "import_from_statement")
    call_node_types = ("call",)

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
            elif t in self.import_node_types:
                imports.extend(
                    self._import_refs_from_node(node, source_lines, filepath)
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
        name = name_node.text.decode()
        sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
        kind = "method" if self._is_method(node) else "function"
        return Symbol(
            name=name,
            kind=kind,
            file=str(filepath),
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=sig,
            language="python",
        )

    def _symbol_from_class_node(
        self, node, source_lines: List[str], filepath: Path
    ) -> Symbol | None:
        name_node = node.child_by_field_name("name")
        if not name_node:
            return None
        name = name_node.text.decode()
        sig = source_lines[node.start_point[0]].rstrip() if source_lines else ""
        return Symbol(
            name=name,
            kind="class",
            file=str(filepath),
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            signature=sig,
            language="python",
        )

    def _import_refs_from_node(
        self, node, source_lines: List[str], filepath: Path
    ) -> List[ImportRef]:
        refs: List[ImportRef] = []
        line = source_lines[node.start_point[0]].strip() if source_lines else ""
        if node.type == "import_from_statement":
            names = [
                c.text.decode()
                for c in node.children
                if c.type in ("dotted_name", "aliased_import", "identifier")
                and c != node.children[1]
            ]
            for name in names:
                refs.append(
                    ImportRef(symbol_name=name, file=str(filepath), import_line=line)
                )
        else:
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    refs.append(
                        ImportRef(
                            symbol_name=child.text.decode(),
                            file=str(filepath),
                            import_line=line,
                        )
                    )
        return refs

    def _call_site_from_node(
        self, node, source_lines: List[str], filepath: Path
    ) -> CallSite | None:
        func_node = node.child_by_field_name("function")
        if not func_node:
            return None
        full_name = func_node.text.decode()
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
        return n.startswith("test_") or n.endswith("_test.py")

    def _is_method(self, func_node) -> bool:
        """True if the function is defined inside a class body."""
        parent = func_node.parent
        while parent:
            if parent.type == "class_definition":
                return True
            if parent.type == "module":
                break
            parent = parent.parent
        return False
