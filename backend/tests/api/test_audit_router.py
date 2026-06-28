# -*- coding: utf-8 -*-
"""
Audit Router 序列化测试。
"""

from app.api.routers.audit import serialize_audit_log
from app.storage.models.agent_audit_log import AgentAuditLog


def test_serialize_audit_log_includes_subagent_parent_metadata() -> None:
    audit_log = AgentAuditLog(
        project_id="project-1",
        session_id="child-thread-1",
        parent_session_id="parent-session-1",
        child_run_id="child-run-1",
        agent_node="writer",
        model_id="gpt-test",
        status="success",
    )

    response = serialize_audit_log(audit_log)

    assert response.parent_session_id == "parent-session-1"
    assert response.child_run_id == "child-run-1"
