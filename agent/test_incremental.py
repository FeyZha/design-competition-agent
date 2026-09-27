"""Run: python platform/competition-agent/test_incremental.py. Only temporary JSON + mocked HTTP/models."""
import base64
import copy
import io
import json
import tempfile
from contextlib import redirect_stdout
from datetime import date
from html import escape
from pathlib import Path
from unittest.mock import patch

import httpx

import agent


class ClockDate(date):
    current = date(2026, 9, 16)

    @classmethod
    def today(cls):
        return cls.current


def rejected(call):
    try:
        call()
    except (ValueError, OSError):
        return
    raise AssertionError("Expected rejection")


def row(number, title="海报设计赛", deadline="2099-01-01"):
    return {"id": str(number), "title": title, "category": "视觉传达", "deadline": deadline, "sourceUrl": f"https://www.shejijingsai.com/2026/09/{number}.html"}


def html(rows, countdown="剩余 10 天"):
    return "<table>" + "".join(f'<tr><td>【{entry["category"]}】</td><td><a href="{entry["sourceUrl"]}">{escape(entry["title"])}</a></td><td>{entry["deadline"] or "待定"}</td><td>{countdown}</td></tr>' for entry in rows) + "</table>"


result = agent.Extraction(eligibility_status="eligible", title="已整理竞赛", directions=[agent.SubmissionDirection(
    title="海报赛道", source_heading="海报赛道", eligibility_status="eligible", independence="confirmed",
    theme_task="设计海报", submission_format="JPG", work_items=[agent.WorkItem(name="海报", kind="visual_design", role="primary", requirement="required", delivery="design_files", evidence=agent.SourceEvidence(url=row(1)["sourceUrl"], quote="海报"))], evidence=[agent.SourceEvidence(url=row(1)["sourceUrl"], quote="测试规则")])])
page = {"html": "", "status": 200}
requests = []


def fetch(request):
    assert str(request.url) == agent.SOURCE_URL, "The startup check must request only the list page"
    requests.append(str(request.url))
    return httpx.Response(page["status"], text=page["html"], request=request)


with tempfile.TemporaryDirectory(prefix="competition-incremental-") as directory, patch.object(agent, "date", ClockDate), patch.object(agent, "ensure_public_url", side_effect=lambda value: value), patch.object(agent, "source_client", side_effect=lambda: httpx.Client(transport=httpx.MockTransport(fetch))), patch.object(agent, "competition_model") as model, patch.object(agent, "crawl") as crawl, patch.object(agent, "extract") as extract:
    path = Path(directory) / "report.json"
    model.return_value = (object(), "test-only")
    assert agent.drain_queue(path, {})["discovery"]["queue"] == []
    model.assert_not_called()

    assert agent.load_report(path)["discovery"]["outputLogicVersion"] == agent.OUTPUT_LOGIC_VERSION

    probe = """
import os, sys
with open(sys.argv[1], 'r+b') as handle:
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(3)
"""
    command = [agent.sys.executable, "-c", probe, str(path.with_suffix(".json.lock"))]
    with agent.report_lock(path):
        assert agent.subprocess.run(command, capture_output=True).returncode == 3, "A separate process must not acquire a held lock"
    assert agent.subprocess.run(command, capture_output=True).returncode == 0, "The lock must be released after each action"

    original, new, expired = row(1), row(2), row(3, deadline="2020-01-01")
    report = agent.load_report(path)
    del report["discovery"]  # A pre-existing JSON report establishes known URL baselines.
    report["items"] = [agent.report_from(original, result, [], [original["sourceUrl"]])[1]]
    report["ignored"] = [{"sourceUrl": expired["sourceUrl"], "reason": "已截止"}]
    agent.save_report(path, report)
    page["html"] = html([original, new, expired])
    checked = agent.check_updates(path)
    assert checked["discovery"]["checkedOn"] == "2026-09-16"
    assert [entry["candidate"]["id"] for entry in checked["discovery"]["queue"]] == ["2"]
    model.assert_not_called()
    crawl.assert_not_called()
    extract.assert_not_called()
    before = path.read_bytes()
    page["html"] = "This is deliberately not a list"
    assert agent.check_updates(path) == agent.load_report(path)
    assert len(requests) == 1 and path.read_bytes() == before, "Same-day restarts must not scan or change an already calibrated report"

    # A catalogue correction is saved even after today's list check, without recrawling or touching evidence/queue.
    calibration_path = Path(directory) / "calibration.json"
    calibration = copy.deepcopy(checked)
    calibration["aClassSourceUrl"] = "https://cis.hutb.edu.cn/old-school-catalog.pdf"
    calibration["items"][0].update(title="2026新锐设计竞赛·华灿奖", priority="recognized", recognized=True)
    calibration["recognizedNames"] = ["两岸新锐设计竞赛·华灿奖"]
    calibration["pending"] = [{**calibration["items"][0], "id": "4", "title": "GCROSS创意金星奖", "sourceUrl": row(4)["sourceUrl"], "pendingReason": "费用待确认", "priority": "a_class", "recognized": False}]
    calibration["pending"][0]["directions"] = [{**direction, "id": "4:track", "directionId": "4:track", "competitionId": "4"} for direction in calibration["pending"][0]["directions"]]
    agent.save_report(calibration_path, calibration)
    corrected = agent.check_updates(calibration_path)
    expected = copy.deepcopy(calibration)
    expected["aClassSourceUrl"] = agent.A_CLASS_SOURCE_URL
    expected["items"][0]["priority"] = "a_class"
    expected["pending"][0].pop("priority")
    assert corrected == expected and json.loads(calibration_path.read_text("utf-8")) == expected
    assert len(requests) == 1, "Reclassification must use saved titles, not network requests"
    model.assert_not_called()
    crawl.assert_not_called()
    extract.assert_not_called()

    ClockDate.current = date(2026, 9, 17)
    original = {**original, "title": "海报设计赛（延期）", "deadline": "2099-02-01"}
    new = {**new, "title": "新海报设计赛"}
    expired = {**expired, "deadline": "2099-03-01"}
    page["html"] = html([original, new, expired])
    checked = agent.check_updates(path)
    assert {entry["candidate"]["id"] for entry in checked["discovery"]["queue"]} == {"2"}, "Known titles/deadlines and ignored records are never refreshed"
    assert len(checked["items"]) == 1 and checked["items"][0]["title"] == "已整理竞赛"
    assert checked["discovery"]["queue"][0]["candidate"]["title"] == "海报设计赛", "Queued source metadata is not rewritten from list changes"
    stable = agent.parse_list(html([original], "剩余 100 天"))[0]
    assert agent.candidate_fingerprint(stable) == agent.candidate_fingerprint(agent.parse_list(html([original], "剩余 99 天"))[0])
    assert agent.candidate_fingerprint(stable) == agent.candidate_fingerprint({**stable, "title": "  " + stable["title"] + "\n"})

    ClockDate.current = date(2026, 9, 18)
    before = copy.deepcopy(checked)
    for invalid in ("<html>site unavailable</html>", "<table></table>"):
        page["html"] = invalid
        rejected(lambda: agent.check_updates(path))
        failed = agent.load_report(path)
        assert failed["discovery"]["checkedOn"] == "2026-09-17"
        assert failed["discovery"]["fingerprints"] == before["discovery"]["fingerprints"]
        assert failed["discovery"]["queue"] == before["discovery"]["queue"] and failed["items"] == before["items"]
        assert failed["discovery"]["checkError"]
    page.update(status=503, html=html([original]))
    rejected(lambda: agent.check_updates(path))
    page["status"] = 200
    checked = agent.check_updates(path)
    assert checked["discovery"]["checkError"] == ""
    assert len(checked["discovery"]["queue"]) == 1, "Unfinished new entries stay queued"

    def resources(_client, url):
        if url == new["sourceUrl"]:
            return [], [], []
        return [{"url": url, "text": "测试规则", "binary": "", "kind": "html"}], [url], [url]

    crawl.side_effect = resources
    extract.side_effect = lambda _llm, candidate, _resources, _model, _audit: result.model_copy(update={"title": candidate["title"], "eligibility_status": "ineligible" if candidate["id"] == "3" else "eligible", "directions": [] if candidate["id"] == "3" else result.directions})
    drained = agent.drain_queue(path, {"provider": "test-only"})
    assert drained["discovery"]["lastBatch"] == {"processed": 0, "failed": 1}
    assert len(drained["items"]) == 1 and drained["items"][0]["title"] == "已整理竞赛", drained
    assert len(drained["ignored"]) == 1 and drained["ignored"][0]["reason"] == "已截止"
    assert [entry["candidate"]["id"] for entry in drained["discovery"]["queue"]] == ["2"]
    assert drained["discovery"]["queue"][0]["lastError"]
    assert extract.call_count == 0, "No resources means failure before LLM extraction"
    assert agent.load_report(path) == drained

    # Routine invocations do not retry failures; a targeted user retry does.
    crawl.side_effect = lambda _client, url: ([{"text": "测试规则"}], [url], [url])
    extract.side_effect = lambda *_args: result.model_copy(update={"eligibility_status": "unclear"})
    model.reset_mock()
    assert agent.drain_queue(path, {"provider": "test-only"}) == drained
    model.assert_not_called()
    drained = agent.drain_queue(path, {"provider": "test-only", "competitionId": "2"})
    assert drained["discovery"]["lastBatch"] == {"processed": 1, "failed": 0}
    assert drained["discovery"]["queue"] == [] and len(drained["pending"]) == 1
    model.assert_called_once()
    model.reset_mock()
    agent.drain_queue(path, {})
    model.assert_not_called()

    ClockDate.current = date(2026, 9, 19)
    original["deadline"] = "2099-04-01"
    page["html"] = html([original])
    checked = agent.check_updates(path)
    good_item = copy.deepcopy(checked["items"][0])
    assert checked["discovery"]["queue"] == [], "Deadline changes alone do not enqueue old competitions"
    checked["discovery"]["outputLogicVersion"] = "old-output-logic"
    agent.save_report(path, checked)
    checked = agent.check_updates(path)
    assert checked["discovery"]["queue"] == [], "Changing output logic must not enqueue old competitions"
    model.reset_mock()
    agent.drain_queue(path, {})
    model.assert_not_called()
    assert agent.check_updates(path, force=True)["discovery"]["queue"] == [], "The ordinary Update button remains incremental"
    checked = agent.check_updates(path, full_refresh=True)
    assert len(checked["discovery"]["queue"]) == 3, "Only an explicit full refresh reprocesses saved and excluded competitions"
    assert all(entry["reprocess"] for entry in checked["discovery"]["queue"])
    old_bytes = path.read_bytes()
    model.side_effect = ValueError("No selected model")
    rejected(lambda: agent.drain_queue(path, {}))
    assert path.read_bytes() == old_bytes
    model.side_effect = None
    extract.side_effect = ValueError("Do not persist provider secrets in an error")
    failed = agent.drain_queue(path, {"provider": "test-only"})
    assert failed["items"][0] == good_item
    assert failed["discovery"]["queue"][0]["lastError"] and "secrets" not in json.dumps(failed)
    assert failed["discovery"]["lastBatch"] == {"processed": 0, "failed": 3}
    ClockDate.current = date(2026, 9, 20)
    original["title"] = "再次修订的海报赛"
    page["html"] = html([original])
    checked = agent.check_updates(path)
    assert len(checked["discovery"]["queue"]) == 3
    assert checked["discovery"]["queue"][0]["lastError"] == failed["discovery"]["queue"][0]["lastError"]
    assert checked["discovery"]["queue"][0]["candidate"]["title"] == good_item["title"]

    # Import merges with the latest report after extraction rather than overwriting concurrent work.
    def imported_names(*_args):
        latest = agent.load_report(path)
        latest["recognizedNames"].append("其他窗口导入的竞赛")
        agent.save_report(path, latest)
        return ["本次导入的竞赛"]

    request = {"action": "importRecognition", "provider": "test-only", "pdfBase64": base64.b64encode(b"%PDF-test-only").decode()}
    with patch.object(agent, "extract_recognized_competitions", side_effect=imported_names), patch.dict(agent.os.environ, {"COMPETITION_REPORT_FILE": str(path)}), patch.object(agent.sys, "stdin", io.StringIO(json.dumps(request))), redirect_stdout(io.StringIO()):
        agent.main()
    assert agent.load_report(path)["recognizedNames"] == ["其他窗口导入的竞赛", "本次导入的竞赛"]
    assert len(agent.load_report(path)["discovery"]["queue"]) == 3

    # Failed atomic replacement leaves the last good file untouched.
    before = path.read_bytes()
    with patch.object(Path, "replace", side_effect=OSError("simulated write failure")):
        rejected(lambda: agent.save_report(path, agent.load_report(path)))
    assert path.read_bytes() == before
    for invalid in ("{", "[]", '{"version":99}', '{"version":1,"items":{},"pending":[],"ignored":[]}', json.dumps({**agent.load_report(path), "discovery": {"queue": "broken"}})):
        path.write_text(invalid, "utf-8")
        rejected(lambda: agent.check_updates(path))
        rejected(lambda: agent.drain_queue(path, {}))
        assert path.read_text("utf-8") == invalid, "Never replace malformed or unknown report data"
        path.write_bytes(before)

    # The CLI startup action itself must not resolve credentials or create an LLM.
    model.reset_mock()
    with patch.dict(agent.os.environ, {"COMPETITION_REPORT_FILE": str(path)}), patch.object(agent.sys, "stdin", io.StringIO('{"action":"checkUpdates"}')), redirect_stdout(io.StringIO()):
        agent.main()
    model.assert_not_called()

    # Changed source deadlines and failed full-refresh records are skipped by ordinary updates.
    ClockDate.current = date(2026, 9, 21)
    original["deadline"] = "2020-01-01"
    page["html"] = html([original, row(90, deadline="2020-01-01")])
    checked = agent.check_updates(path)
    assert [entry["candidate"]["id"] for entry in checked["discovery"]["queue"]] == ["1", "2", "3"]
    assert checked["items"][0] == good_item
    extract.side_effect = lambda *_args: result.model_copy(update={"directions": []})
    drained = agent.drain_queue(path, {"provider": "test-only"})
    assert drained["items"][0] == good_item
    assert drained["discovery"]["queue"] == checked["discovery"]["queue"]

    # Saved failure placeholders do not implicitly trigger old-data backfill.
    retry_path = Path(directory) / "retry.json"
    retry_report = agent.load_report(retry_path)
    failed_candidate = row(91)
    retry_report["pending"] = [{**agent.report_from(failed_candidate, result, [], [failed_candidate["sourceUrl"]])[1], "pendingReason": "信息提取失败，等待重试"}]
    agent.save_report(retry_path, retry_report)
    page["html"] = html([failed_candidate])
    model.reset_mock()
    checked = agent.check_updates(retry_path)
    assert checked["discovery"]["queue"] == []
    model.assert_not_called()

    # Ignore known category changes, while still excluding brand-new non-graphic entries.
    agent.drain_queue(retry_path, {"provider": "test-only"})
    ClockDate.current = date(2026, 9, 22)
    failed_candidate["category"] = "工业产品"
    page["html"] = html([failed_candidate, {**row(92), "category": "工业产品"}])
    assert agent.parse_list(page["html"]) == []
    checked = agent.check_updates(retry_path)
    assert checked["discovery"]["queue"] == []
    extract.side_effect = lambda *_args: result.model_copy(update={"eligibility_status": "ineligible", "directions": []})
    drained = agent.drain_queue(retry_path, {"provider": "test-only", "competitionId": "91"})
    assert drained["items"] == [] and drained["ignored"][0]["reason"] == "在校生不可参加"

    # Explicit refresh bypasses today's successful scan; ordinary requests reuse it.
    manual_path = Path(directory) / "manual.json"
    manual_candidate = row(501)
    page["html"] = html([manual_candidate])
    agent.check_updates(manual_path)
    extract.side_effect = lambda *_args: result
    agent.drain_queue(manual_path, {"provider": "test-only"})
    model.reset_mock()
    crawl.reset_mock()
    extract.reset_mock()
    request_count = len(requests)
    agent.check_updates(manual_path)
    assert len(requests) == request_count
    unchanged = agent.check_updates(manual_path, force=True)
    assert len(requests) == request_count + 1 and unchanged["discovery"]["queue"] == []
    agent.drain_queue(manual_path, {})
    model.assert_not_called()
    crawl.assert_not_called()
    extract.assert_not_called()

    manual_candidate["title"] = "主动更新发现的修订命题"
    page["html"] = html([manual_candidate])
    with patch.dict(agent.os.environ, {"COMPETITION_REPORT_FILE": str(manual_path)}), patch.object(agent.sys, "stdin", io.StringIO('{"action":"checkUpdates","forceCheck":true}')), redirect_stdout(io.StringIO()):
        agent.main()
    manual = agent.load_report(manual_path)
    assert len(requests) == request_count + 2
    assert manual["discovery"]["queue"] == [], "Explicit ordinary refresh is still new-only, not full refresh"
    assert manual["items"] == unchanged["items"], "Source checks only enqueue, never replace good details"
    model.assert_not_called()

    # A failed manual check must be retried even if an earlier same-day check succeeded.
    page["html"] = "<html>source temporarily unavailable</html>"
    rejected(lambda: agent.check_updates(manual_path, force=True))
    failed = agent.load_report(manual_path)
    assert failed["discovery"]["checkError"] and failed["discovery"]["checkedOn"] == ClockDate.today().isoformat()
    assert failed["discovery"]["queue"] == manual["discovery"]["queue"]
    assert failed["items"] == manual["items"]
    page["html"] = html([manual_candidate])
    retried = agent.check_updates(manual_path)
    assert len(requests) == request_count + 4 and retried["discovery"]["checkError"] == ""
    assert retried["discovery"]["queue"] == manual["discovery"]["queue"]
    for invalid_force in ('"true"', "1", "null"):
        with patch.dict(agent.os.environ, {"COMPETITION_REPORT_FILE": str(manual_path)}), patch.object(agent.sys, "stdin", io.StringIO('{"action":"checkUpdates","forceCheck":' + invalid_force + '}')), redirect_stdout(io.StringIO()):
            rejected(agent.main)
        with patch.dict(agent.os.environ, {"COMPETITION_REPORT_FILE": str(manual_path)}), patch.object(agent.sys, "stdin", io.StringIO('{"action":"checkUpdates","fullRefresh":' + invalid_force + '}')), redirect_stdout(io.StringIO()):
            rejected(agent.main)
    assert len(requests) == request_count + 4
    with patch.dict(agent.os.environ, {"COMPETITION_REPORT_FILE": str(manual_path)}), patch.object(agent.sys, "stdin", io.StringIO('{"action":"checkUpdates","fullRefresh":true}')), redirect_stdout(io.StringIO()):
        agent.main()
    manual_full = agent.load_report(manual_path)
    assert len(manual_full["discovery"]["queue"]) == 1 and manual_full["discovery"]["queue"][0]["reprocess"]
    assert manual_full["items"] == manual["items"]
    model.assert_not_called()

print("Incremental checks passed: seen-source skip, no version-triggered reprocessing, explicit full refresh/retry and protected JSON/import writes.")
