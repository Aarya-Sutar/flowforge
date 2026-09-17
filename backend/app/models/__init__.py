"""Import every model module here so SQLAlchemy's mapper registry is fully populated
before any relationship (declared by string, e.g. relationship("ExtractedEntity")) is
resolved — regardless of which module happens to be imported first at runtime."""
from app.models import (  # noqa: F401
    audit_log,
    extracted_entity,
    processing_run,
    request,
    user,
    workflow_rule,
    workflow_task,
)
