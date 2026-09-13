"""
Domain layer — the single source of truth for RecoverAI's shared vocabulary.

Every enum, the normalized event shape, and the decision contract live here.
Nothing outside this package should redefine an equivalent string constant —
import from here instead. See AGENTS.md "Source-of-truth files".

This package has NO dependency on SQLAlchemy, FastAPI, Celery, or Razorpay.
It is pure Python + Pydantic so it can be imported anywhere (models, schemas,
services, workers) without pulling in unrelated infrastructure.
"""
