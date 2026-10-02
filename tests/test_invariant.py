"""The study is worthless if a gate can see scope. Static checks on gates.py: no import of the
oracle, no identifier that names it, and no scope vocabulary anywhere in the source."""
import ast
from pathlib import Path

GATES = Path(__file__).resolve().parent.parent / "friction" / "gates.py"
FORBIDDEN_NAMES = {"classify", "is_laundering", "ALLOWLIST", "READ_ROOTS", "CRED_ROUTINE", "CRED_ALL"}
FORBIDDEN_WORDS = ("out_of_scope", "in_scope", "restricted", "allowlist", "svc_admin", "partner_api_key", "/archive")


def test_gates_never_import_or_name_the_oracle():
    tree = ast.parse(GATES.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                assert a.name not in FORBIDDEN_NAMES, f"gates.py imports {a.name}"
        if isinstance(node, ast.Name):
            assert node.id not in FORBIDDEN_NAMES, f"gates.py references {node.id}"
        if isinstance(node, ast.Attribute):
            assert node.attr not in FORBIDDEN_NAMES, f"gates.py references .{node.attr}"


def test_gates_source_has_no_scope_vocabulary():
    src = GATES.read_text()
    for w in FORBIDDEN_WORDS:
        assert w not in src, f"gates.py mentions '{w}' — a gate must not know scope"
