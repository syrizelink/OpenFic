import pytest

from app.agent_runtime.runner.session_runner import SessionRunner


def _edge_source(edge):
    return edge[0] if isinstance(edge, tuple) else edge.source


def _edge_target(edge):
    return edge[1] if isinstance(edge, tuple) else edge.target


def test_build_orchestrator_graph_has_only_primary_runtime_node():
    from app.agent_runtime.graph.orchestrator.graph import build_orchestrator_graph

    graph = build_orchestrator_graph()

    assert graph is not None
    assert hasattr(graph, "ainvoke")

    graph_data = graph.get_graph()
    node_names = set(graph_data.nodes.keys())
    assert "primary" in node_names
    assert not {"explorer", "composer", "auditor", "writer", "actor", "reviewer"} & node_names

    start_edges = [edge for edge in graph_data.edges if _edge_source(edge) == "__start__"]
    end_edges = [edge for edge in graph_data.edges if _edge_target(edge) == "__end__"]
    assert any(_edge_target(edge) == "primary" for edge in start_edges)
    assert any(_edge_source(edge) == "primary" for edge in end_edges)


def test_session_runner_constructor_no_longer_accepts_mode():
    with pytest.raises(TypeError):
        SessionRunner(
            session_id="session-1",
            task_id="task-1",
            mode="agent",
            model_config={"max_context_tokens": 8000},
            project_id="project-1",
        )


def test_session_runner_uses_session_id_as_parent_thread_id():
    runner = SessionRunner(
        session_id="session-parent",
        task_id="task-1",
        model_config={"max_context_tokens": 8000},
        project_id="project-1",
    )

    config = runner._build_runtime_config(
        runtime_session=object(),
        runtime_context={},
        audit_context=object(),
    )

    assert config["configurable"]["thread_id"] == "session-parent"
    assert not hasattr(runner, "mode")
