from shiftchain.agent import AGENT_NAME, ShiftChainToolRuntime, build_agent
from shiftchain.demo import run_demo
from shiftchain.frozen_data import frozen_repository


class OfflineParserStub:
    route = type("Route", (), {"name": "offline", "project": None, "location": None})()


def test_exactly_one_adk_agent_with_four_tools() -> None:
    runtime = ShiftChainToolRuntime(frozen_repository(), OfflineParserStub())
    agent = build_agent(runtime)
    assert agent.name == AGENT_NAME == "shiftchain_agent"
    assert len(agent.tools) == 4
    assert not agent.sub_agents


def test_cli_demo_frozen_results() -> None:
    result = run_demo()
    states = {item["source_event_id"]: item["state"] for item in result["results"]}
    assert states == {
        "EVT-001": "VERIFIED",
        "EVT-002": "VERIFIED",
        "EVT-003": "WAITING_CONFIRMATION",
        "EVT-004": "VERIFIED",
        "AMB-001": "NEEDS_CLARIFICATION",
    }
    assert result["custody_SHF_260826_E"] == ["W-001", "W-002", "W-003"]
    assert result["schedule_version"] == 2

