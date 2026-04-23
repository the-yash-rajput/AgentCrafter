import os

from .imports import CASES as IMPORT_CASES
from .dunders import CASES as DUNDER_CASES
from .eval_exec import CASES as EVAL_EXEC_CASES
from .file_io import CASES as FILE_IO_CASES
from .subprocess_net import CASES as SUBPROCESS_NET_CASES
from .resource_exhaustion import CASES as RESOURCE_EXHAUSTION_CASES
from .helper_module_walks import CASES as HELPER_MODULE_CASES
from .restricted_python_edge import CASES as RESTRICTED_EDGE_CASES
from .write_guard import CASES as WRITE_GUARD_CASES
from .payload_tricks import CASES as PAYLOAD_CASES
from .asyncio_tricks import CASES as ASYNCIO_CASES

_RUN_DANGEROUS = os.environ.get("RUN_DANGEROUS_TESTS") == "1"

ALL_CASES = tuple(
    case
    for case in (
        IMPORT_CASES
        + DUNDER_CASES
        + EVAL_EXEC_CASES
        + FILE_IO_CASES
        + SUBPROCESS_NET_CASES
        + RESOURCE_EXHAUSTION_CASES
        + HELPER_MODULE_CASES
        + RESTRICTED_EDGE_CASES
        + WRITE_GUARD_CASES
        + PAYLOAD_CASES
        + ASYNCIO_CASES
    )
    if _RUN_DANGEROUS or not case.dangerous
)
