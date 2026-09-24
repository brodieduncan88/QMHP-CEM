# Copyright (c) 2026 Brodie Duncan. All rights reserved.
# Proprietary QMHP-CEM source. No licence is granted except by explicit written agreement.
"""Serve the read-only evidence viewer.

    python -m frontend                      # this checkout, http://127.0.0.1:8765
    python -m frontend --repo /path --port 9000

Binds to the loopback interface unless ``--host`` says otherwise. There is no
flag that enables writing, execution or approval: that code does not exist.
"""

from __future__ import annotations

import argparse
import os
import sys

from .server import make_server


def main(argv: list[str] | None = None) -> int:
    default_repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(prog="python -m frontend", description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=default_repo, help="repository checkout to display")
    parser.add_argument("--host", default="127.0.0.1", help="interface to bind (default loopback)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--quiet", action="store_true", help="suppress the request log")
    args = parser.parse_args(argv)

    server = make_server(args.repo, args.host, args.port, quiet=args.quiet)
    host, port = server.server_address[:2]
    print(f"QMHP-CEM read-only viewer: http://{host}:{port}/  (repository {os.path.abspath(args.repo)})")
    print("GET/HEAD only. No execution, approval or write path exists. Ctrl-C to stop.")
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"warning: bound to {args.host}; the repository's contents are visible to that network.",
              file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
