"""Run: python -X utf8 platform/competition-agent/test_directions.py. No live models or data writes."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
from langchain_core.runnables import RunnableLambda

import agent

url = "https://www.shejijingsai.com/2026/05/1545002.html"
candidate = {"id": "1545002", "title": "测试综合赛", "sourceUrl": url, "category": "综合设计", "deadline": "2099-01-01"}
blocks = ["（一）乡村文旅用品与纪念品组\n要求：每个作品不少于4张，格式为JPG或GIF，每张大小不超过10M；\n以乡村文化设计纪念品。", "（二）乡村特产包装设计组\n要求：以PDF文件形式提交，大小不超过50M；\n设计乡村特产包装。"]
resource = {"url": url, "text": "\n".join(blocks), "kind": "html", "binary": ""}
common = dict(eligibility_status="eligible", deadline="2099-01-01", deadline_status="exact", fee="免费", fee_status="free")
def work(name, quote, kind="visual_design", role="primary", requirement="required", delivery="design_files"):
    return agent.WorkItem(name=name, kind=kind, role=role, requirement=requirement, delivery=delivery, evidence=agent.SourceEvidence(url=url, quote=quote))


directions = [agent.SubmissionDirection(**common, title=block.splitlines()[0], source_heading=block.splitlines()[0], independence="confirmed", design_types=["文创" if index == 0 else "包装"], theme_task=block.splitlines()[2], submission_format=block.splitlines()[1], evidence=[dict(url=url, quote=block)], work_items=[work("纪念品" if index == 0 else "包装", block, "product_concept" if index == 0 else "visual_design")]) for index, block in enumerate(blocks)]
result = agent.Extraction(**common, title=candidate["title"], directions=directions)
directions[0].final_submission_format = 'A3竖版展板，1至2张，300dpi，JPG，单张不超过10MB'
_, final_report = agent.report_from(candidate, result, [url], [url])
assert final_report['directions'][0]['finalSubmissionFormat'] == directions[0].final_submission_format
assert final_report['directions'][1]['finalSubmissionFormat'] == '', 'Do not invent A3 or inherit a sibling track specification'
assert not agent.valid_record({**final_report, 'finalSubmissionFormat': 3}, True)
assert agent.validate_directions(result, [resource]) is result

category_theme = '所属设计领域：交叉创新设计\n作品类别：\n1. 跨学科设计（科技+艺术融合、新材料创新应用等）；\n2. 社会创新设计（公益项目、无障碍设计等）；\n3. 未来概念设计（太空探索、未来城市等）。'
category_resource = {**resource, 'text': category_theme}
categories = [agent.CreativeCategory(title=title, description=line, evidence=agent.SourceEvidence(url=url, quote=line), work_items=[work(title, line)]) for title, line in zip(['跨学科设计', '社会创新设计', '未来概念设计'], category_theme.splitlines()[2:])]
category_direction = directions[0].model_copy(update={'title': '交叉创新设计', 'source_heading': '交叉创新设计', 'theme_task': category_theme, 'evidence': [agent.SourceEvidence(url=url, quote=category_theme)], 'work_items': [work('作品类别', category_theme, 'unknown', requirement='unclear', delivery='unspecified')], 'creative_categories': categories})
category_result = agent.validate_directions(result.model_copy(update={'directions': [category_direction]}), [category_resource])
assert [category.title for category in category_direction.creative_categories] == ['跨学科设计', '社会创新设计', '未来概念设计']
assert '无障碍设计' in category_direction.creative_categories[1].description
_, category_report = agent.report_from(candidate, category_result, [url], [url])
assert agent.valid_record(category_report, True)
serialized_categories = category_report['directions'][0]['creativeCategories']
assert len(serialized_categories) == 3
omitted_category = category_result.model_copy(deep=True)
omitted_category.directions[0].creative_categories.pop()
try:
    agent.validate_directions(omitted_category, [category_resource])
except agent.DirectionValidationError as error:
    assert '遗漏创作类别' in str(error)
else:
    raise AssertionError('An omitted numbered creative category was accepted')
assert not agent.listed_creative_categories(category_theme.replace('作品类别：', '提交清单：'), [category_resource]), 'Deliverables are not optional choices'
assert not agent.listed_creative_categories(category_theme, [{**resource, 'text': '没有类别原文'}]), 'Never infer categories without source evidence'
for invalid_categories in [[{**serialized_categories[0], 'id': ''}], [serialized_categories[0]] * 2, [{**serialized_categories[0], 'evidence': {'url': url, 'quote': '虚构名称'}}]]:
    assert not agent.valid_record({**category_report['directions'][0], 'creativeCategories': invalid_categories}, True)
fabricated = category_result.model_copy(deep=True)
fabricated.directions[0].creative_categories[0].title = '虚构类别'
try:
    agent.validate_directions(fabricated, [category_resource])
except agent.DirectionValidationError as error:
    assert '原文依据' in str(error)
else:
    raise AssertionError('A fabricated creative category was accepted')

bound_headings = ["任务一：AIGC品牌短片设计", "任务二：AIGC视觉海报设计"]
binding = "参赛选手需同时完成以下两项内容："
bound_text = binding + "\n" + "\n".join(bound_headings)
bound_resource = {**resource, "text": bound_text}
bundle = directions[0].model_copy(update={"title": "AIGC品牌短片设计＋AIGC视觉海报设计", "source_heading": bound_headings[0], "source_headings": bound_headings, "binding_evidence": agent.SourceEvidence(url=url, quote=binding), "evidence": [agent.SourceEvidence(url=url, quote=bound_text)], "submission_format": "品牌短片：MP4，1—3分钟\n视觉海报：JPG，1-4幅\n制作报告：PDF，500字以内", "work_items": [work("AIGC品牌短片设计", bound_text, "video", delivery="finished_media"), work("AIGC视觉海报设计", bound_text)]})
bound_result = result.model_copy(update={"directions": [bundle]})
assert agent.validate_directions(bound_result, [bound_resource]) is bound_result
assert not bundle.creative_categories, 'Mandatory film and poster deliveries are never optional categories'
_, bound_report = agent.report_from(candidate, bound_result, [url], [url])
assert len(bound_report["directions"]) == 1
assert bound_report["directions"][0]["sourceHeadings"] == bound_headings
assert bound_report["directions"][0]["bindingEvidence"]["quote"] == binding
assert "MP4" in bound_report["directions"][0]["submissionFormat"] and "JPG" in bound_report["directions"][0]["submissionFormat"]
assert bound_report["directions"][0]["creationSupport"]["status"] == "partial"
assert "AIGC品牌短片设计" in bound_report["directions"][0]["creationSupport"]["reason"]
for bad in [
    [bundle.model_copy(update={"source_headings": [], "binding_evidence": None})],
    [bundle.model_copy(update={"binding_evidence": agent.SourceEvidence(url=url, quote="无依据的绑定")})],
    [bundle, bundle.model_copy(update={"title": "单独海报", "source_heading": bound_headings[1], "source_headings": [], "binding_evidence": None})],
]:
    try:
        agent.validate_directions(bound_result.model_copy(update={"directions": bad}), [bound_resource])
    except agent.DirectionValidationError:
        pass
    else:
        raise AssertionError("Split, fabricated or duplicated bundled tasks were accepted")
assert not agent.bound_submission_sections(bound_text.replace("同时完成", "选择完成")), "Optional tasks must remain separate"
missing_film = bundle.model_copy(update={"work_items": [work("AIGC视觉海报设计", bound_headings[1])]})
try:
    agent.validate_directions(bound_result.model_copy(update={"directions": [missing_film]}), [bound_resource])
except agent.DirectionValidationError as error:
    assert "绑定任务缺少对应作品事实" in str(error)
else:
    raise AssertionError("A bound film cannot disappear from the decision facts while remaining only in the task text")


def rejected(value, message):
    try:
        agent.validate_directions(value, [resource])
    except agent.DirectionValidationError as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError("Invalid direction extraction was accepted")

rejected(result.model_copy(update={"directions": directions[1:]}), "遗漏原文组别")
numbered = "1、短视频创作赛道\n2、创意产品设计赛道\n3、平面IP形象赛道"
assert agent.submission_sections(numbered) == numbered.splitlines()
try:
    agent.validate_directions(result, [{**resource, "text": numbered}])
except agent.DirectionValidationError as error:
    assert "遗漏原文组别" in str(error) and "平面IP形象赛道" in str(error)
else:
    raise AssertionError("Arabic-numbered tracks must also be checked for omission")
numeric_block = "3、平面IP形象赛道\n格式要求：以JPG、PNG或GIF提交，每张不超过10M。"
numeric_direction = directions[0].model_copy(update={"source_heading": numeric_block.splitlines()[0], "submission_format": "JPG、PNG，每张不超过10M", "evidence": [agent.SourceEvidence(url=url, quote=numeric_block)]})
try:
    agent.validate_directions(result.model_copy(update={"directions": [numeric_direction]}), [{**resource, "text": numeric_block}])
except agent.DirectionValidationError as error:
    assert "交付数量或格式" in str(error)
else:
    raise AssertionError("Format requirements under numeric track headings cannot lose GIF")
bad_count = result.model_copy(deep=True)
bad_count.directions[0].submission_format = bad_count.directions[0].submission_format.replace("不少于4张", "4张")
rejected(bad_count, "交付数量或格式")
bad_evidence = result.model_copy(deep=True)
bad_evidence.directions[0].evidence[0].quote = "编造的原文"
rejected(bad_evidence, "原文中定位")
for mutation, reason in [
    ({"work_items": []}, "缺少主体作品事实"),
    ({"work_items": [work("纪念品", blocks[0], role="supporting")]}, "缺少主体作品事实"),
    ({"work_items": [work("纪念品", blocks[0], requirement="optional")]}, "缺少主体作品事实"),
    ({"work_items": [work("没有的作品名", blocks[0])]}, "作品名称缺少原文依据"),
    ({"work_items": [work("纪念品", "虚构纪念品") ]}, "作品依据无法在已获取原文中定位"),
]:
    invalid = result.model_copy(deep=True)
    invalid.directions[0] = invalid.directions[0].model_copy(update=mutation)
    rejected(invalid, reason)
wrong_url = result.model_copy(deep=True)
wrong_url.directions[0].work_items[0].evidence.url = 'https://example.test/unfetched'
rejected(wrong_url, "作品依据无法在已获取原文中定位")
common_source = {**category_resource, 'text': category_theme + '\n各类别必须提交实物样品。'}
common_result = category_result.model_copy(deep=True)
required_sample = work('实物样品', '各类别必须提交实物样品。', 'physical', 'supporting', delivery='physical_object')
common_result.directions[0].work_items.append(required_sample)
try:
    agent.validate_directions(common_result, [common_source])
except agent.DirectionValidationError as error:
    assert '遗漏共通必交作品' in str(error)
else:
    raise AssertionError('A category cannot omit the common required physical sample')
for category in common_result.directions[0].creative_categories:
    category.work_items.append(required_sample.model_copy(deep=True))
assert agent.validate_directions(common_result, [common_source]) is common_result
_, common_report = agent.report_from(candidate, common_result, [url], [url])
assert all(category['creationSupport']['status'] == 'partial' for category in common_report['directions'][0]['creativeCategories'])
weakened = common_result.model_copy(deep=True)
weakened.directions[0].creative_categories[0].work_items[-1].requirement = 'optional'
try:
    agent.validate_directions(weakened, [common_source])
except agent.DirectionValidationError as error:
    assert '遗漏共通必交作品' in str(error)
else:
    raise AssertionError('A category cannot weaken a common required item to optional')

uncertain = result.model_copy(deep=True)
uncertain.directions[0].independence = "unclear"
assert not agent.validate_directions(uncertain, [resource]).directions[0].missing_information, "Do not infer a task blocker from a metadata flag alone"
supplemented = result.model_copy(deep=True)
supplemented.directions[0].missing_information = ["素材包未读取", "未提供邮寄地址和评审细则"]
_, supplementary_report = agent.report_from(candidate, supplemented, [url], [url])
assert supplementary_report["directions"][0]["pendingReason"] == ""
assert supplementary_report["directions"][0]["missingInformation"] == supplemented.directions[0].missing_information
supplemented.directions[0].submission_format = "未公布"
_, incomplete_report = agent.report_from(candidate, supplemented, [url], [url])
assert incomplete_report["directions"][0]["pendingReason"] == "", "Existing work facts establish deliverables even when file specifications are absent"
assert incomplete_report["directions"][0]["submissionFormat"] == "- 必交：纪念品"
_, report = agent.report_from(candidate, result, [url], [url])
_, reordered = agent.report_from(candidate, result.model_copy(update={"directions": list(reversed(directions))}), [url], [url])
assert len({item["id"] for item in report["directions"]}) == 2
assert {item["title"]: item["id"] for item in report["directions"]} == {item["title"]: item["id"] for item in reordered["directions"]}
assert report["directions"][0]["designTypes"] == ["文创"]
assert "PDF" not in report["directions"][0]["submissionFormat"]
assert "JPG" not in report["directions"][1]["submissionFormat"]
calls = []
def reply(messages):
    calls.append(messages)
    payload = result.model_dump()
    if len(calls) == 1:
        payload["directions"] = payload["directions"][1:]
    return json.dumps(payload, ensure_ascii=False)
assert len(agent.extract(RunnableLambda(reply), candidate, [resource], "test").directions) == 2
assert len(calls) == 2 and "遗漏原文组别" in calls[1][-1].content
assert not agent.should_follow("https://www.cdec.org.cn/contestDetail", "大赛介绍", False)
assert agent.should_follow("https://storage.example.test/rules.pdf", "正式文件下载", False)
unread = result.model_copy(deep=True)
agent.validate_directions(unread, [resource, {"url": "https://example.test/rules.pdf", "kind": "unread", "text": "", "binary": ""}])
assert all(not direction.missing_information for direction in unread.directions), "An unread attachment does not invalidate every complete task"
with tempfile.TemporaryDirectory() as folder:
    calls.clear()
    agent.extract(RunnableLambda(reply), candidate, [resource], "test", Path(folder))
    attempts = [json.loads(path.read_text('utf-8')) for path in sorted(Path(folder).glob('*.json'))]
    assert len(attempts) == 2 and "遗漏原文组别" in attempts[0]['validationError'] and attempts[0]['output']
    assert not attempts[1]['validationError']

with tempfile.TemporaryDirectory() as folder:
    path = Path(folder) / "report.json"
    saved = agent.load_report(path)
    saved["items"] = [{**candidate, "themeTask": "原任务书"}]
    other = {**candidate, "id": "other", "sourceUrl": "https://www.shejijingsai.com/2026/05/99.html"}
    saved["discovery"]["queue"] = [{"candidate": other, "fingerprint": agent.candidate_fingerprint(other), "discoveredAt": "test"}]
    agent.save_report(path, saved)
    with patch.object(agent, "competition_model", return_value=(object(), "test")), patch.object(agent, "source_client", return_value=httpx.Client()), patch.object(agent, "crawl", return_value=([resource], [url], [url])) as crawl, patch.object(agent, "extract", side_effect=agent.DirectionValidationError("遗漏原文组别")):
        failed = agent.drain_queue(path, {"competitionId": candidate["id"]})
        assert failed["items"][0]["themeTask"] == "原任务书"
        assert failed["discovery"]["lastBatch"] == {"processed": 0, "failed": 1}
        assert crawl.call_count == 1
    with patch.object(agent, "competition_model", return_value=(object(), "test")), patch.object(agent, "source_client", return_value=httpx.Client()), patch.object(agent, "crawl", side_effect=AssertionError("Retry should reuse saved source")), patch.object(agent, "extract", return_value=result):
        updated = agent.drain_queue(path, {"competitionId": candidate["id"]})
        assert len(updated["items"][0]["directions"]) == 2
        assert [entry["candidate"]["id"] for entry in updated["discovery"]["queue"]] == ["other"]
        assert updated["items"][0]["sourceVersion"]
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder) / "report.json"
    old = agent.load_report(path)
    version = "a" * 64
    old["items"] = [{**candidate, "themeTask": "旧摘要", "sourceVersion": version}]
    old["discovery"].update(checkedOn=agent.date.today().isoformat(), fingerprints={url: agent.candidate_fingerprint(candidate)})
    agent.save_report(path, old)
    old = agent.load_report(path)
    agent.save_report(path.parent / "source-snapshots" / f"{version}.json", dict(resources=[resource], sources=[url], knownUrls=[url]))
    with patch.object(agent, "source_client", side_effect=AssertionError("Same-day backfill must not rescan the list")), patch.object(agent, "competition_model") as model:
        queued = agent.check_updates(path)
        assert queued["discovery"]["queue"] == [], "Incremental updates must skip saved summaries, even without directions"
        assert queued["items"] == old["items"], "Queueing must preserve old summaries"
        queued["discovery"]["outputLogicVersion"] = "previous-logic"
        agent.save_report(path, queued)
        queued = agent.check_updates(path)
        assert queued["discovery"]["queue"] == [], "Logic changes alone must never reprocess saved reports"
        assert agent.drain_queue(path, {})["discovery"]["queue"] == []
        queued = agent.check_updates(path, full_refresh=True)
        assert [entry["candidate"]["id"] for entry in queued["discovery"]["queue"]] == [candidate["id"]]
        assert queued["discovery"]["queue"][0]["reprocess"] is True
        assert agent.check_updates(path)["discovery"]["queue"] == queued["discovery"]["queue"], "Routine checks retain explicitly queued work without duplicating it"
        model.assert_not_called()
    def prepared(*_args):
        saved = agent.load_report(path)
        assert saved["discovery"]["queue"][0]["sourceVersion"], "Capture is saved before model processing, so restart can resume"
        assert not saved["items"][0].get("directions"), "Unvalidated data is not published early"
        return result
    with patch.object(agent, "competition_model", return_value=(object(), "test")), patch.object(agent, "source_client", return_value=httpx.Client()), patch.object(agent, "crawl", side_effect=AssertionError("Use the captured source")), patch.object(agent, "extract", side_effect=prepared):
        ready = agent.drain_queue(path, {})
    assert not ready["discovery"]["queue"]
    assert len(next(item for item in ready["items"] if item["id"] == candidate["id"])["directions"]) == 2
    assert not agent.prepare_update_queue(ready), "Completed work does not repeat under the same output logic"

print("Direction checks passed: source validation, incremental skip, explicit full refresh, cached-source reuse and atomic publication.")
