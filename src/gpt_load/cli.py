import argparse, asyncio, json, os, sys
from . import paths

# Importing models/web pulls in Flask-SQLAlchemy, so do it inside the
# subcommands: "python cli.py --help" must work before those deps load.
def cmd_run(args):
    from .loadgen.engine import LoadEngine
    from .loadgen.metrics import MODEL_COSTS, summarize
    from .loadgen.scenarios import load_scenario

    sc = load_scenario(args.scenario)
    eng = LoadEngine(sc["endpoint"], sc["model"], sc.get("api_key", ""),
                     sc["concurrency"], sc["duration"], sc.get("rpm", 1000), sc.get("tpm", 500000))
    asyncio.run(eng.run())
    s = summarize(eng.samples)
    print(f"[gpt-load] rps={s['rps']} p50={s['p50']}ms p95={s['p95']}ms p99={s['p99']}ms err={s['err_rate']}% cost=${s['cost']}")

def cmd_report(args):
    """Print stored runs, newest first."""
    from .models import Run
    from ._app import app

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

def cmd_compare(args):
    """Line up the summary metrics of two stored runs."""
    from .models import Run
    from ._app import app

    with app.app_context():
        a = Run.query.filter_by(id=args.run_a).first()
        b = Run.query.filter_by(id=args.run_b).first()
    if a is None or b is None:
        print("both run ids must exist", file=sys.stderr)
        return 2
    sa = json.loads(a.summary_json or "{}")
    sb = json.loads(b.summary_json or "{}")
    print("%-12s%12s%12s%12s" % ("metric", "#%d" % a.id, "#%d" % b.id, "delta"))
    for k in sorted(set(sa) | set(sb)):
        va, vb = sa.get(k, 0), sb.get(k, 0)
        try:
            delta = "%.2f" % (float(vb) - float(va))
        except (TypeError, ValueError):
            delta = "-"
        print("%-12s%12s%12s%12s" % (k, va, vb, delta))
    return 0

def main():
    p = argparse.ArgumentParser(prog="gpt-load")
    sub = p.add_subparsers(dest="cmd")
    r = sub.add_parser("run"); r.add_argument("scenario")
    rp = sub.add_parser("report")
    rp.add_argument("--limit", type=int, default=20)
    rp.add_argument("--json", action="store_true")
    cp = sub.add_parser("compare")
    cp.add_argument("run_a", type=int); cp.add_argument("run_b", type=int)
    args = p.parse_args()
    if args.cmd == "run":
        return cmd_run(args)
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "compare":
        return cmd_compare(args)
    p.print_help()
    return 1
