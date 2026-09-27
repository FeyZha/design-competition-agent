"""Run: python platform/competition-agent/test_config.py. No network or report writes."""
import json
from types import SimpleNamespace
from unittest.mock import patch

import agent
from langchain_core.messages import HumanMessage


def rejected(call, text):
    try:
        call()
    except ValueError as error:
        assert text in str(error), str(error)
    else:
        raise AssertionError("Expected rejection")


with patch.dict(agent.os.environ, {"DEEPSEEK_API_KEY": "must-not-be-used"}):
    rejected(lambda: agent.competition_model({}), "偏好设置")
    rejected(lambda: agent.competition_model({"provider": "api", "apiFormat": "openai"}), "API Key")

with patch.object(agent, "ChatOpenAI") as api:
    _, model = agent.competition_model({"provider": "api", "apiFormat": "openai", "baseUrl": "https://example.test", "apiKey": "test-only", "model": "chosen-model"})
    assert model == "chosen-model"
    assert api.call_args.kwargs["base_url"] == "https://example.test/v1"
    assert api.call_args.kwargs["api_key"] == "test-only"

with patch.object(agent.shutil, "which", return_value=None):
    rejected(lambda: agent.competition_model({"provider": "codex"}), "未找到")

with patch.object(agent.shutil, "which", return_value="codex.exe"), patch.object(agent.subprocess, "run") as run:
    run.return_value = SimpleNamespace(returncode=1)
    rejected(lambda: agent.competition_model({"provider": "codex"}), "尚未登录")
    run.return_value = SimpleNamespace(returncode=0)
    llm, model = agent.competition_model({"provider": "codex"})
    assert model == "codex"
    event = {"type": "item.completed", "item": {"type": "agent_message", "text": '{"names":["测试设计竞赛"]}'}}
    run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(event))
    with patch.object(agent, "PdfReader", return_value=SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "测试设计竞赛")])):
        assert agent.extract_recognized_competitions(llm, b"test-only", model) == ["测试设计竞赛"]
    args, kwargs = run.call_args
    assert "--ignore-user-config" in args[0] and "--ephemeral" in args[0]
    assert "read-only" in args[0] and "features.shell_tool=false" in args[0]
    assert 'web_search="disabled"' in args[0]
    assert "测试设计竞赛" in kwargs["input"]
    assert not agent.Path(kwargs["cwd"]).exists(), "Temporary context must be cleaned up"
    run.return_value = SimpleNamespace(returncode=0, stdout='{"type":"turn.failed"}')
    rejected(lambda: llm.invoke([HumanMessage(content="test")]), "未完成")
    run.return_value = SimpleNamespace(returncode=0, stdout="")
    rejected(lambda: llm.invoke([HumanMessage(content="test")]), "有效内容")

agent.self_check()
print("Config checks passed: explicit provider, no env fallback, selected API, Codex login/isolation/parser, existing extraction rules.")
