"""Publishes a new tone for every report, without a redeploy.

Each run adds a version and makes it the active one; old versions stay for
the audit trail. The next question in any open chat uses the new tone.

    uv run --frozen python scripts/set_persona.py "Write in short bullet points. Be direct."
    uv run --frozen python scripts/set_persona.py --show
"""

import argparse
import os
import sys

import psycopg
from dotenv import load_dotenv


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("instructions", nargs="?", help="the new tone instructions")
    parser.add_argument("--name", default="default")
    parser.add_argument("--show", action="store_true", help="print every version and exit")
    args = parser.parse_args()
    load_dotenv()

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        if args.show or not args.instructions:
            rows = conn.execute(
                "select version, active, created_at, instructions from personas where name = %s order by version",
                (args.name,),
            ).fetchall()
            for version, active, created, text in rows:
                print(f"v{version}{' (active)' if active else ''} {created:%Y-%m-%d %H:%M}: {text}")
            return 0
        conn.execute("update personas set active = false where active")
        (version,) = conn.execute(
            "insert into personas (name, version, instructions, active) "
            "select %s, coalesce(max(version), 0) + 1, %s, true from personas where name = %s returning version",
            (args.name, args.instructions, args.name),
        ).fetchone() or (0,)
    print(f"Persona {args.name} v{version} is now active.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
