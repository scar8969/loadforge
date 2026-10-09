"""The project's own Flask application: models, routes and background runs.

Kept separate from ``gpt_load.app`` on purpose: this module is the legacy
surface the factory wraps, so it stays importable and testable on its own.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import traceback
from typing import Any

from flask import (Flask, Response, flash, jsonify, redirect, render_template,
                   request, stream_with_context, url_for)

from . import paths
from .loadgen.engine import LoadEngine
from .loadgen.metrics import MODEL_COSTS, summarize
from .models import Run, Sample, db, utc_now

paths.ensure_runtime_dirs()


def build_app() -> Flask:
    """Build the application: configuration, database, then routes."""
    app = Flask(__name__, template_folder=str(paths.TEMPLATES_DIR),
                instance_path=str(paths.INSTANCE_DIR))
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + str(paths.INSTANCE_DIR / "gptload.db")
    app.secret_key = os.environ.get("SECRET_KEY", "gpt-load-dev")
    db.init_app(app)
    with app.app_context():
        db.create_all()

    _engines: dict[int, LoadEngine] = {}  # run_id -> LoadEngine

    @app.context_processor
    def _inject_app_name() -> dict[str, Any]:
        return {"app_name": "gpt-load"}

    @app.get("/api/health")
    def health() -> Any:
        return jsonify({"status": "ok", "runs": Run.query.count(),
                        "samples": Sample.query.count()})

    @app.post("/api/runs")
    def create_run() -> Any:
        d = request.get_json(force=True, silent=True) or {}
        run = Run(scenario=d.get("scenario", "basic"), endpoint=d.get("endpoint", ""),
                  model=d.get("model", "gpt-4o"), concurrency=d.get("concurrency", 20),
                  duration=d.get("duration", 60))
        db.session.add(run)
        db.session.commit()
        eng = LoadEngine(run.endpoint, run.model, d.get("api_key", ""),
                         run.concurrency, run.duration, d.get("rpm", 1000), d.get("tpm", 500000))
        _engines[run.id] = eng
        threading.Thread(target=_run_async, args=(run.id,), daemon=True).start()
        return jsonify({"run_id": run.id, "status": "running"})

    def _run_async(run_id: int) -> None:
        # The thread outlives the request that started it, so it cannot rely on
        # the request context: it opens its own application context instead.
        with app.app_context():
            run = Run.query.get(run_id)
            eng = _engines.get(run_id)
            try:
                if eng is not None and run is not None:
                    asyncio.run(eng.run())
                if run is not None:
                    run.status = "done"
                    run.finished_at = utc_now()
                    run.summary_json = json.dumps(
                        summarize(eng.samples) if eng is not None else {})
            except Exception:
                traceback.print_exc()
                if run is not None:
                    run.status = "failed"
                    run.finished_at = utc_now()
            db.session.commit()

    @app.get("/api/runs")
    def list_runs() -> Any:
        return jsonify({"runs": [r.to_dict() for r in Run.query.order_by(Run.id.desc()).limit(50).all()]})

    @app.get("/api/runs/<int:rid>/stream")
    def stream(rid: int) -> Response:
        def gen() -> Any:
            while True:
                run = Run.query.get(rid)
                yield f"data: {json.dumps({'status': run.status, 'summary': json.loads(run.summary_json or '{}')})}\n\n"
                if run.status != "running":
                    break
        # The body is consumed after the request context has been torn down, so
        # it has to be wrapped: without stream_with_context the database lookup
        # inside the generator sees no current application.
        return Response(stream_with_context(gen()), mimetype="text/event-stream")

    @app.post("/api/runs/<int:rid>/stop")
    def stop(rid: int) -> Any:
        eng = _engines.get(rid)
        if eng:
            eng.stop()
        return jsonify({"status": "stopped"})

    @app.get("/")
    def index() -> Any:
        runs = [(r, json.loads(r.summary_json or "{}"))
                for r in Run.query.order_by(Run.id.desc()).limit(8).all()]
        counts = {"runs": Run.query.count(), "samples": Sample.query.count(),
                  "running": Run.query.filter_by(status="running").count()}
        defaults = {"scenario": "basic",
                    "endpoint": "http://127.0.0.1:8080/v1/chat/completions",
                    "model": "gpt-4o", "concurrency": 20, "duration": 10,
                    "rpm": 1000, "tpm": 500000}
        return render_template("index.html", runs=runs, counts=counts,
                               models=sorted(MODEL_COSTS), defaults=defaults)

    @app.post("/run")
    def start_run() -> Any:
        f = request.form

        def _int(name: str, default: int) -> int:
            try:
                return int(f.get(name) or default)
            except (TypeError, ValueError):
                return default

        run = Run(scenario=f.get("scenario", "basic"), endpoint=f.get("endpoint", ""),
                  model=f.get("model", "gpt-4o"), concurrency=_int("concurrency", 20),
                  duration=_int("duration", 10))
        db.session.add(run)
        db.session.commit()
        eng = LoadEngine(run.endpoint, run.model, f.get("api_key", ""),
                         run.concurrency, run.duration, _int("rpm", 1000), _int("tpm", 500000))
        _engines[run.id] = eng
        threading.Thread(target=_run_async, args=(run.id,), daemon=True).start()
        flash("started run #%d" % run.id, "success")
        return redirect(url_for("index"))

    @app.get("/history")
    def history() -> Any:
        runs = [(r, json.loads(r.summary_json or "{}"))
                for r in Run.query.order_by(Run.id.desc()).limit(100).all()]
        return render_template("history.html", runs=runs)

    @app.get("/compare")
    def compare() -> Any:
        runs = [(r, json.loads(r.summary_json or "{}"))
                for r in Run.query.order_by(Run.id.desc()).limit(50).all()]

        def _pick(name: str) -> Any:
            try:
                rid = int(request.args.get(name, ""))
            except (TypeError, ValueError):
                return None
            return Run.query.get(rid)

        left, right = _pick("a"), _pick("b")
        metric_rows = []
        if left is not None and right is not None:
            sa = json.loads(left.summary_json or "{}")
            sb = json.loads(right.summary_json or "{}")
            for k in sorted(set(sa) | set(sb)):
                va, vb = sa.get(k), sb.get(k)
                try:
                    delta = float(vb) - float(va)
                except (TypeError, ValueError):
                    delta = None
                metric_rows.append({"label": k, "a": va, "b": vb, "delta": delta})
        return render_template("compare.html", runs=runs, left=left, right=right,
                               metric_rows=metric_rows)

    @app.post("/runs/<int:rid>/stop")
    def stop_run(rid: int) -> Any:
        eng = _engines.get(rid)
        if eng:
            eng.stop()
        run = Run.query.get(rid)
        if run is not None and run.status == "running":
            run.status = "stopped"
            run.finished_at = utc_now()
            db.session.commit()
        flash("stopped run #%d" % rid, "success")
        return redirect(url_for("history"))

    @app.post("/runs/<int:rid>/delete")
    def delete_run(rid: int) -> Any:
        Sample.query.filter_by(run_id=rid).delete()
        run = Run.query.get(rid)
        if run is not None:
            db.session.delete(run)
            db.session.commit()
        flash("deleted run #%d" % rid, "success")
        return redirect(url_for("history"))

    return app


app = build_app()
