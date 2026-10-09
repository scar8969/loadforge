import argparse
import asyncio
import json
import os
import sys
from typing import Any


# Importing models/web pulls in Flask-SQLAlchemy, so do it inside the
# subcommands: "python cli.py --help" must work before those deps load.
def cmd_run(args: argparse.Namespace) -> int:
    from ._app import app
    from .loadgen.engine import LoadEngine
    from .loadgen.metrics import summarize
    from .loadgen.scenarios import load_scenario
    from .models import Run, db, utc_now

    sc = load_scenario(args.scenario)
    eng = LoadEngine(sc["endpoint"], sc["model"], sc.get("api_key", ""),
                     sc["concurrency"], sc["duration"], sc.get("rpm", 1000), sc.get("tpm", 500000))
    asyncio.run(eng.run())
    s = summarize(eng.samples)
    print(f"[gpt-load] rps={s['rps']} p50={s['p50']}ms p95={s['p95']}ms p99={s['p99']}ms err={s['err_rate']}% cost=${s['cost']}")

    # Persist the run before exiting: without this row the "report" and
    # "compare" subcommands would have nothing to read back, which would make
    # the documented run -> report -> compare flow useless.
    with app.app_context():
        run = Run(scenario=os.path.basename(args.scenario), endpoint=sc["endpoint"],
                  model=sc["model"], status="done",
                  concurrency=sc["concurrency"], duration=sc["duration"],
                  summary_json=json.dumps(s), finished_at=utc_now())
        db.session.add(run)
        db.session.commit()
        print(f"[gpt-load] recorded run #{run.id}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Print stored runs, newest first."""
    from ._app import app
    from .models import Run

    with app.app_context():
        rows = Run.query.order_by(Run.id.desc()).limit(args.limit).all()
        out = [{"id": r.id, "scenario": r.scenario, "model": r.model,
                "status": r.status,
                "summary": json.loads(r.summary_json or "{}")} for r in rows]
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        for r in out:
            print(f"#{r['id']} {r['scenario']:<16} {r['model']:<14} "
                  f"{r['status']:<8} {r['summary']}")
    return 0


def _as_float(value: Any) -> float:
    """Coerce one side of a comparison to a number.

    Metrics are read back from JSON, so a value here is a number, a numeric
    string, or the ``None`` left behind by a key only one run recorded. The
    missing side counts as zero so the delta still reports how far the other
    run moved; a value that is present but not numeric raises ``ValueError``
    and the delta column degrades to ``"-"`` instead of inventing a number."""
    return 0.0 if value is None else float(value)


def cmd_compare(args: argparse.Namespace) -> int:
    """Line up the summary metrics of two stored runs."""
    from ._app import app
    from .models import Run

    with app.app_context():
        a = Run.query.filter_by(id=args.run_a).first()
        b = Run.query.filter_by(id=args.run_b).first()
    if a is None or b is None:
        print("both run ids must exist", file=sys.stderr)
        return 2
    sa: dict[str, Any] = json.loads(a.summary_json or "{}")
    sb: dict[str, Any] = json.loads(b.summary_json or "{}")
    print("%-12s%12s%12s%12s" % ("metric", "#%d" % a.id, "#%d" % b.id, "delta"))
    for k in sorted(set(sa) | set(sb)):
        # A key that only one side carried stays visible, printed with the
        # other side blank rather than being dropped: the missing half counts
        # as zero so the delta is still the distance the recorded half moved.
        va, vb = sa.get(k), sb.get(k)
        try:
            delta = "%.2f" % (_as_float(vb) - _as_float(va))
        except (TypeError, ValueError):
            delta = "-"
        print("%-12s%12s%12s%12s" % (k, va, vb, delta))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="gpt-load")
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("run")
    r.add_argument("scenario")
    rp = sub.add_parser("report")
    rp.add_argument("--limit", type=int, default=20)
    rp.add_argument("--json", action="store_true")
    cp = sub.add_parser("compare")
    cp.add_argument("run_a", type=int)
    cp.add_argument("run_b", type=int)
    args = p.parse_args(argv)
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "compare":
        return cmd_compare(args)
    p.print_help()
    return 1


if __name__ == "__main__":
    # ``python -m gpt_load.cli`` must behave exactly like the console script;
    # argparse exits with code 2 for an unknown argument, so the exit status is
    # propagated instead of being discarded.
    sys.exit(main())
