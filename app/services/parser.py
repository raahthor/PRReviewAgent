from dataclasses import dataclass
from pathlib import PurePosixPath

from tree_sitter import Language, Parser
import tree_sitter_javascript as ts_javascript
import tree_sitter_python as ts_python
import tree_sitter_typescript as ts_typescript


@dataclass
class Symbol:
    name: str
    symbol_type: str
    signature: str | None
    start_line: int
    end_line: int


LANGUAGES = {
    ".py": Language(ts_python.language()),
    ".js": Language(ts_javascript.language()),
    ".jsx": Language(ts_javascript.language()),
    ".ts": Language(ts_typescript.language_typescript()),
    ".tsx": Language(ts_typescript.language_tsx()),
}

# Pre-instantiate parsers once rather than recreating per file
PARSERS = {ext: Parser(lang) for ext, lang in LANGUAGES.items()}

SYMBOL_TYPES = {
    # Python
    "function_definition": "function",
    "class_definition": "class",
    # JavaScript / TypeScript
    "function_declaration": "function",
    "class_declaration": "class",
    "method_definition": "method",
    "interface_declaration": "interface",
    "type_alias_declaration": "type",
    "enum_declaration": "enum",
}


def extract_symbols(
    file_path: str,
    content: str,
) -> list[Symbol]:
    extension = PurePosixPath(file_path).suffix
    parser = PARSERS.get(extension)

    if parser is None:
        return []

    tree = parser.parse(content.encode("utf-8"))
    lines = content.splitlines()

    symbols: list[Symbol] = []
    _walk_tree(
        node=tree.root_node,
        lines=lines,
        symbols=symbols,
    )
    return symbols


def _walk_tree(
    node,
    lines: list[str],
    symbols: list[Symbol],
) -> None:
    symbol_type = SYMBOL_TYPES.get(node.type)

    if symbol_type:
        name_node = _get_name_node(node)

        if name_node:
            symbols.append(
                Symbol(
                    name=name_node.text.decode("utf-8"),
                    symbol_type=symbol_type,
                    signature=_get_signature(node, lines),
                    start_line=node.start_point.row + 1,
                    end_line=node.end_point.row + 1,
                )
            )

    for child in node.children:
        _walk_tree(
            node=child,
            lines=lines,
            symbols=symbols,
        )


def _get_name_node(node):
    # Tree-Sitter grammars standard field name
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return name_node

    for child in node.children:
        if child.type in {"identifier", "property_identifier", "type_identifier"}:
            return child

    return None


def _get_signature(node, lines: list[str]) -> str | None:
    start = node.start_point.row
    if start >= len(lines):
        return None

    # Signatures reside in the declaration header (bound to 15 lines max)
    end = min(node.end_point.row + 1, len(lines), start + 15)
    declaration = " ".join(line.strip() for line in lines[start:end])

    depth = 0
    cut = len(declaration)

    for i, ch in enumerate(declaration):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "{" and depth == 0:
            cut = i
            break
        elif (
            ch == ":"
            and depth == 0
            and node.type in ("function_definition", "class_definition")
        ):
            cut = i + 1
            break

    declaration = declaration[:cut].strip()
    return declaration or None
