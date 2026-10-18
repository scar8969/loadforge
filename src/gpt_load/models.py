import datetime as _datetime
from typing import Any

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# flask_sqlalchemy builds the declarative base lazily inside init_app and stores
# it as an instance attribute, so db.Model is invisible to a static checker and
# every db.Column below would be flagged. Binding it once, to a plainly
# Any-typed alias, keeps the rest of the module checkable; the gpt_load.models
# override in pyproject.toml turns off disallow_subclassing_any for this module
# because the base genuinely is dynamic.
Base: Any = db.Model


def utc_now() -> _datetime.datetime:
    """Current UTC time as a naive datetime.

    The columns below are naive ``DateTime`` values, so the value stored must be
    naive too; ``datetime.utcnow()`` did exactly that but was removed in Python
    3.12+ in favour of the timezone-aware constructors used here.
    """
    return _datetime.datetime.now(_datetime.UTC).replace(tzinfo=None)


class Run(Base):
    __tablename__ = "runs"
    id = db.Column(db.Integer, primary_key=True)
    scenario = db.Column(db.String(128), default="")
    endpoint = db.Column(db.String(256), default="")
    model = db.Column(db.String(64), default="")
    status = db.Column(db.String(16), default="running")  # running|done|stopped|failed
    concurrency = db.Column(db.Integer, default=20)
    duration = db.Column(db.Integer, default=60)
    started_at = db.Column(db.DateTime, default=utc_now)
    finished_at = db.Column(db.DateTime, nullable=True)
    summary_json = db.Column(db.Text, default="{}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scenario": self.scenario,
            "model": self.model,
            "status": self.status,
            "concurrency": self.concurrency,
            "duration": self.duration,
            "started_at": self.started_at.isoformat() if self.started_at else "",
            "finished_at": self.finished_at.isoformat() if self.finished_at else "",
            "summary": self.summary_json,
        }


class Sample(Base):
    __tablename__ = "samples"
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("runs.id"), index=True)
    ts = db.Column(db.Float, default=0.0)
    latency_ms = db.Column(db.Float, default=0.0)
    status = db.Column(db.Integer, default=0)  # 0 ok, 1 error, 2 timeout
    status_code = db.Column(db.Integer, default=0)
    tokens_in = db.Column(db.Integer, default=0)
    tokens_out = db.Column(db.Integer, default=0)
