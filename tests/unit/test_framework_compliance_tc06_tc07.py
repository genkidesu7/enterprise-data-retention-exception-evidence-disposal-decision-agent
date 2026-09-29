# CMN-C2-672 — Framework Compliance (TC) tests per docs/03_test_spec.md

import ast
import os
import re

import pytest

from framework.nodes.function_node import FunctionNode


def test_tc06_security_gate_input_cannot_be_overridden():
    """TC-06: overriding _security_gate_input() on a FunctionNode subclass raises TypeError."""
    with pytest.raises(TypeError):

        class BadInputNode(FunctionNode):
            def execute(self, state):
                return {}

            def _security_gate_input(self, state):
                return state


def test_tc07_security_gate_output_cannot_be_overridden():
    """TC-07: overriding _security_gate_output() on a FunctionNode subclass raises TypeError."""
    with pytest.raises(TypeError):

        class BadOutputNode(FunctionNode):
            def execute(self, state):
                return {}

            def _security_gate_output(self, result):
                return result


_CREDENTIAL_PATTERN = re.compile(r"(jwt|token|api_key|secret|password|credential|connection_string)", re.IGNORECASE)


def _find_python_files(directory: str) -> list[str]:
    py_files = []
    for root, _dirs, files in os.walk(directory):
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))
    return py_files


def test_tc03_no_credential_field_assignments_on_state_object():
    """TC-03: no field named jwt/token/api_key/secret/password/credential is
    assigned as a State dict key anywhere under src/nodes/ or src/services/."""
    violations: list[str] = []
    for base in ("src/nodes", "src/services"):
        src_dir = os.path.join(os.path.dirname(__file__), "..", "..", base)
        if not os.path.exists(src_dir):
            continue
        for filepath in _find_python_files(src_dir):
            with open(filepath) as f:
                tree = ast.parse(f.read(), filename=filepath)
            for node in ast.walk(tree):
                if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "state":
                    key = node.slice
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        if _CREDENTIAL_PATTERN.search(key.value):
                            violations.append(f"{filepath}:{node.lineno} — state[{key.value!r}] assignment")

    assert violations == [], f"Credential-in-state violations:\n" + "\n".join(violations)


def test_tc04_invocation_context_not_read_from_state_configurable_key():
    """TC-04: nodes obtain InvocationContext via InvocationContext.from_state(state),
    never by reading a raw 'configurable' key directly out of the node's local state dict."""
    src_dir = os.path.join(os.path.dirname(__file__), "..", "..", "src", "nodes")
    violations: list[str] = []
    for filepath in _find_python_files(src_dir):
        with open(filepath) as f:
            source = f.read()
        if 'state["configurable"]' in source or "state['configurable']" in source:
            violations.append(f"{filepath}: reads state['configurable'] directly")

    assert violations == [], f"InvocationContext boundary violations:\n" + "\n".join(violations)
