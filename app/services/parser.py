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

# pre instantiate parsers once so they're reused across all files
PARSERS = {ext: Parser(lang) for ext, lang in LANGUAGES.items()}

# maps tree-sitter node type names to simpler symbol type names
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
    
    # parse and return all top level symbols (functions, classes, etc.)
    extension = PurePosixPath(file_path).suffix
    parser = PARSERS.get(extension)

    # unsupported language, nothing to parse
    if parser is None:
        return []

    tree = parser.parse(content.encode("utf-8"))
    lines = content.splitlines()

    symbols: list[Symbol] = []

    _walk_tree(node=tree.root_node, lines=lines, symbols=symbols)
    return symbols


def _walk_tree(node, lines: list[str], symbols: list[Symbol]) -> None:

    # recursively walk the AST and collect symbol nodes
    symbol_type = SYMBOL_TYPES.get(node.type)

    # if this node is a symbol we care about, extract it
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

    # recurse into child nodes
    for child in node.children:
        _walk_tree(node=child, lines=lines, symbols=symbols)


def _get_name_node(node):
    # find the identifier node that holds this symbol's name

    # tree-Sitter grammars expose a "name" field on most declaration nodes
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return name_node

    # fallback: scan children for any identifier like node
    for child in node.children:
        if child.type in {"identifier", "property_identifier", "type_identifier"}:
            return child

    return None


def _get_signature(node, lines: list[str]) -> str | None:
    # extract just the declaration line(s) of a symbol, without the body
    start = node.start_point.row
    if start >= len(lines):
        return None

    # grab up to 15 lines starting from the symbol declaration
    end = min(node.end_point.row + 1, len(lines), start + 15)

    # take a slice of lines, strip whitespace from each, then join into one string
    # e.g. ["def foo(", "  x: int", ") -> str:"] -> "def foo( x: int ) -> str:"
    header_lines = lines[start:end]
    declaration = " ".join(line.strip() for line in header_lines)

    # walk character by character to find where the header ends and the body starts
    # we track bracket depth so we don't cut inside a parameter list
    depth = 0
    cut = len(declaration)  # default: keep the whole thing

    for i, ch in enumerate(declaration):
        if ch in "([":
            depth += 1  # entering a bracket group
        elif ch in ")]":
            depth -= 1  # leaving a bracket group
        elif ch == "{" and depth == 0:
            # opening brace at top level = start of function/class body (JS/TS style)
            cut = i
            break
        elif (
            ch == ":"
            and depth == 0
            and node.type in ("function_definition", "class_definition")
        ):
            # colon at top level = end of Python def/class header
            cut = i + 1
            break

    declaration = declaration[:cut].strip()
    return declaration or None
