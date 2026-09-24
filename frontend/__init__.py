# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Read-only evidence viewer for the QMHP-CEM repository.

The viewer displays, searches, filters and explains repository data. It cannot
change it. There is no execution path, no approval path, no write path and no
hidden admin mode: the HTTP layer answers GET and HEAD only, the data adapter
opens files for reading only, and nothing here imports the solver, orchestrator,
evaluator, geometry or experiment code. ``tests/test_readonly_frontend.py``
enforces each of those properties.

Layers
------
``repo_fs``   the single filesystem gateway: bounded, path-confined reads.
``classify``  explicit, documented labelling rules (evidence basis, status).
``adapter``   parses records, experiments, approvals and manifests into views.
``server``    a GET/HEAD-only HTTP handler over the adapter and static assets.
"""

__all__ = ["READ_ONLY"]

#: A declaration, not a switch. Nothing in this package reads it to decide
#: whether to write: there is no write code to enable.
READ_ONLY = True
