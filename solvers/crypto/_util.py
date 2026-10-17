"""Console helpers for the crypto solvers: re-exports solvers/serial/_util.py."""
import importlib.util
import os

_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "serial", "_util.py")
_spec = importlib.util.spec_from_file_location("serial_util", _path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

FLAG_RE = _mod.FLAG_RE
PROMPT = _mod.PROMPT
open_console = _mod.open_console
read_until = _mod.read_until
sync = _mod.sync
cmd = _mod.cmd
reset_and_capture = _mod.reset_and_capture
submit = _mod.submit
port_arg = _mod.port_arg
