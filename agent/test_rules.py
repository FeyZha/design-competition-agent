"""Run: python platform/competition-agent/test_rules.py. Mocked model/PDF; temporary report only."""
import base64
import io
import json
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import agent
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError


candidate = {"id": "1", "title": "海报设计竞赛", "category": "综合设计", "deadline": "2099-12-31", "sourceUrl": "https://www.shejijingsai.com/2099/01/1.html"}
base = {"eligibility_status": "eligible", "design_types": ["海报"]}


def reported(**values):
    return agent.report_from(candidate, agent.Extraction(**{**base, **values}), [], [])


def priority(title, **values):
    report = {"items": [{"title": title, **values}], "recognizedNames": []}
    agent.apply_priorities(report)
    return report["items"][0].get("priority")


classification_cases = [
    ("岁岁鸭专项赛", "命题1（IP角色设计：三视图、表情包）；命题2（IP条漫设计：条漫+一幅宣传海报）。", ["海报", "字体"], ["IP/吉祥物", "漫画"]),
    ("临潭县形象标识（LOGO）征集", "征集形象标识（LOGO）成套作品，适配品牌VI手册、包装、海报。", ["包装", "品牌/VI", "字体"], ["标志"]),
    ("中国台球协会新标识（LOGO）设计征集", "设计标识方案，适用于服装和宣传品。", ["品牌/VI", "字体", "标志"], ["标志"]),
    ("青海林草IP形象征集", "打造专属IP形象，适配海报、文创、新媒体。", ["海报", "文创", "品牌/VI"], ["IP/吉祥物"]),
    ("主题海报设计大赛", "需配品牌Logo及口号，遵循VI规范。", ["海报", "标志", "品牌/VI"], ["海报"]),
    ("品牌VI设计征集", "VI基础系统含标准字体、标准配色、Logo。", ["品牌/VI", "字体"], ["品牌/VI"]),
    ("字体设计大赛", "创作原创字体设计作品。", ["字体"], ["字体"]),
    ("IP角色设计大赛", "IP角色设计与插画、包装、海报为独立赛道。", [], ["IP/吉祥物", "插画", "包装"]),
    ("条漫设计竞赛", "命题1（条漫设计：配套宣传海报）；命题2（海报设计：独立海报）。", [], ["漫画", "海报"]),
    ("条漫与海报专项赛", "命题1 （条漫设计：配套宣传海报）；命题2 独立宣传海报设计。", [], ["漫画", "海报"]),
    ("创意竞赛", "提交ZIP文件，图片采用VIP标准。", [], ["综合视觉"]),
    ("潮玩设计赛道", "围绕海洋生物设计潮玩作品。", [], ["文创"]),
    ("纪念品设计赛道", "设计本地旅游纪念品。", [], ["文创"]),
    ("IP角色设计", "创作IP角色，应用场景：潮玩设计、纪念品设计。", ["文创"], ["IP/吉祥物"]),
]
for title, task, proposed, expected in classification_cases:
    assert agent.fixed_design_types(title, task, proposed) == expected, title
    _, classified = reported(title=title, theme_task=task, design_types=proposed, submission_format="文字转曲或嵌入字体；包装保存后附宣传海报。")
    assert classified["designTypes"] == (proposed or ["综合视觉"]) and classified["track"] == "、".join(proposed or ["综合视觉"]), title
    assert classified["themeTask"] == task, "Classification never rewrites the original requirements"
assert reported(title="潮汐回声", theme_task="用流动的弧线回应地方记忆", design_types=["文创"])[1]["designTypes"] == ["文创"], "New records preserve the model's source-based tags without keyword vetoes"


def work(name, kind="visual_design", role="primary", requirement="required", delivery="design_files", quote=None):
    return agent.WorkItem(name=name, kind=kind, role=role, requirement=requirement, delivery=delivery,
        evidence=agent.SourceEvidence(url=candidate["sourceUrl"], quote=quote or name))


support_cases = [
    ("文创设计稿", [work("恐龙潮玩设计稿", "product_concept")], "supported"),
    ("无文件规格", [work("海报", delivery="unspecified")], "supported"),
    ("短片及配图", [work("短片", "video", delivery="finished_media"), work("宣传海报", role="supporting")], "unsupported"),
    ("短片海报共同必交", [work("短片", "video", delivery="finished_media"), work("海报")], "partial"),
    ("文创和实物", [work("设计稿", "product_concept"), work("实物样品", "physical", "supporting", delivery="physical_object")], "partial"),
    ("实物选交", [work("设计稿", "product_concept"), work("实物样品", "physical", "supporting", "optional", "physical_object")], "supported"),
    ("程序必交", [work("视觉设计"), work("运行程序", "functional", "supporting", delivery="runnable")], "partial"),
    ("文档配套", [work("海报"), work("说明书", "document", "supporting", delivery="unspecified")], "supported"),
    ("纯文档", [work("说明书", "document")], "unsupported"),
    ("实物主体", [work("模型", "product_concept", delivery="physical_object")], "unsupported"),
    ("未知主体", [work("作品", "unknown", delivery="unspecified")], "unclear"),
    ("未知关系", [work("设计稿", requirement="unclear")], "unclear"),
    ("选交未知不阻断", [work("海报"), work("其他材料", "unknown", "supporting", "optional", "unspecified")], "supported"),
    ("配套未知提示", [work("海报"), work("其他材料", "unknown", "supporting", delivery="unspecified")], "partial"),
    ("配套必交关系未知", [work("海报"), work("样品", "physical", "supporting", "unclear", "physical_object")], "partial"),
]
with patch.object(agent, "competition_model", side_effect=AssertionError("Support rules must not call a model")):
    for label, facts, expected in support_cases:
        support = agent.classify_creation_support(facts)
        assert support["status"] == expected, (label, support)
        direction = agent.SubmissionDirection(**base, title=label, source_heading=label, independence="confirmed",
            theme_task="保留完整主题", submission_format="保留完整交付", evidence=[facts[0].evidence], work_items=facts)
        status, report = agent.report_from(candidate, direction, [], [])
        assert status == "report", "Creation support never discards the collected source"
        assert report["creationSupport"] == support and report["workItems"] == [fact.model_dump() for fact in facts]
        assert report["themeTask"] == "保留完整主题" and report["submissionFormat"] == "保留完整交付"
        assert "graphicStatus" not in report
        if expected == "partial":
            assert support["reason"].startswith("可在画布完成视觉设计；")
    assert "完成或确认" in support["reason"], "Unclear supporting requirements are not presented as mandatory"
    visual = agent.CreativeCategory(title="海报", description="海报类别", evidence=work("海报").evidence, work_items=[work("海报")])
    video = agent.CreativeCategory(title="短片", description="短片类别", evidence=work("短片").evidence, work_items=[work("短片", "video", delivery="finished_media")])
    choice = direction.model_copy(update={"title": "可选海报或短片", "submission_format": "", "work_items": [work("海报或短片", "unknown", requirement="unclear")], "creative_categories": [visual, video]})
    _, choices = agent.report_from(candidate, choice, [], [])
    assert [category["creationSupport"]["status"] for category in choices["creativeCategories"]] == ["supported", "unsupported"]
    assert choices["creationSupport"] == {"status": "partial", "reason": "部分创作类别可在画布完成，请选择具体创作类别"}
    assert choices["creativeCategories"][0]["workItems"] == [work("海报").model_dump()]
    bound = visual.model_copy(update={"work_items": [work("海报"), work("短片", "video", delivery="finished_media")]})
    _, single = agent.report_from(candidate, choice.model_copy(update={"creative_categories": [bound]}), [], [])
    assert single["creationSupport"] == single["creativeCategories"][0]["creationSupport"] == {"status": "partial", "reason": "可在画布完成视觉设计；另需完成：短片"}
    no_specs = direction.model_copy(update={"theme_task": "创作海报", "submission_format": "", "work_items": [work("海报", delivery="unspecified")]})
    _, no_specs_report = agent.report_from(candidate, agent.Extraction(**base, directions=[no_specs]), [], [])
    assert no_specs_report["directions"][0]["submissionFormat"] == "- 必交：海报"
    assert no_specs_report["directions"][0]["pendingReason"] == ""
    assert no_specs_report["creationSupport"] == {"status": "supported", "reason": ""}
    assert choices["creativeCategories"][0]["submissionFormat"] == "- 必交：海报"
    assert choices["creativeCategories"][1]["submissionFormat"] == "- 必交：短片", "Category summaries never inherit another category's deliverables"
    shared_format = "全部类别提交 JPG，A3 尺寸，300 dpi，每张不超过 10 MB。"
    _, shared = agent.report_from(candidate, choice.model_copy(update={"submission_format": shared_format}), [], [])
    assert all(category["submissionFormat"] == shared_format for category in shared["creativeCategories"]), "Empty category format inherits complete shared specifications before falling back to names"
assert "graphic_status" not in agent.Extraction.model_json_schema()["properties"]
assert "graphic_status" not in agent.SubmissionDirection.model_json_schema()["properties"]


assert len(agent.A_CLASS_COMPETITIONS) == len(set(agent.A_CLASS_COMPETITIONS)) == 84
assert agent.A_CLASS_COMPETITIONS[9] == "全国大学生广告艺术大赛"
assert agent.A_CLASS_COMPETITIONS[15] == "两岸新锐设计竞赛·华灿奖"
assert agent.A_CLASS_COMPETITIONS[33] == "未来设计师·全国高校数字艺术设计大赛"
assert agent.A_CLASS_COMPETITIONS[-1] == "码蹄杯全国职业院校程序设计大赛"
assert agent.A_CLASS_SOURCE_URL.startswith("https://glxy.xhu.edu.cn/")
for title in agent.A_CLASS_COMPETITIONS:
    assert priority(title) == "a_class", title
for title in (
    "2026第14届未来设计师·全国高校数字艺术设计大赛之屈臣氏集团185周年高校AIGC创意专项赛",
    "2026未来设计师·国际创新设计大赛（IIDA）",
    "2026新锐设计竞赛·华灿奖定向主题征集十四：梦瓶",
    "2023中国国际互联网+大学生创新创业大赛",
    "2026第20届中国好创意丨第三届乡村旅游非凡设计专项赛",
    "2026米兰设计周—中国高校设计学科师生优秀作品展",
    "第18届全国大学生广告艺术大赛",
    "2026全国高校商业精英挑战赛—品牌策划竞赛",
    "2026中国高校计算机大赛—人工智能创意赛",
    "外研社·国才杯理解当代中国全国大学生外语能力大赛—英语阅读",
    "2026中国高校计算机大赛",
    "全国高校商业精英挑战赛",
):
    assert priority(title) == "a_class", title
for title in (
    "GCROSS创意金星奖",
    "2026未来设计师·全国高校数字艺术设计教师教学创新竞赛（NDTC）",
    "未来设计师·全国高校数字艺术设计大赛（NDTC）教师赛",
    "未来设计师·全国高校数字艺术设计作品展（NCDE）",
    "全国高校商业精英挑战赛—广告创意大赛",
    "中国高校计算机大赛—电竞锦标赛",
    "外研社·国才杯理解当代中国全国大学生外语能力大赛—日语比赛",
    "第21届好创意丨古建山西潮玩设计大赛",
    "全国大学生广告艺术教师大赛",
):
    assert priority(title) is None, title
assert agent.competition_name_matches("2026新锐设计竞赛·华灿奖", "两岸新锐设计竞赛·华灿奖"), "P1 keeps its existing name matching"
short_title = "2026第21届好创意丨古建山西潮玩设计大赛"
assert priority(short_title, registrationUrl="https://contest.cdec.org.cn") == "a_class"
for url in ("", "https://contest.cdec.org.cn.evil.test", "https://contest.cdec.org.cn@evil.test", "https://unrelated.test", "https://[", "https://[not-an-ip]"):
    assert priority(short_title, registrationUrl=url) is None
assert priority("随便聊聊好创意的其他赛事", registrationUrl="https://contest.cdec.org.cn") is None


for fee, fee_status, expected in [("免费参赛，奖金 10000 元", "free", "free"), ("参赛免费，可自选付费纸质证书，差旅自理", "free", "free"), ("每件作品参赛费 100 元", "paid", "paid"), ("未公布", "unknown", "unknown"), ("", "free", "unknown"), ("待确认", "free", "unknown")]:
    status, item = reported(fee=fee, fee_status=fee_status)
    assert status == "report" and item["feeStatus"] == expected, item
    assert item["fee"] == (fee or "未公布")
assert reported()[1]["feeStatus"] == "unknown", "Missing fees must not become free"
assert reported()[1]["aiAllowed"] is True
assert reported()[1]["aiRule"] == "可以（未发现禁止说明）", "User explicitly retained this rule"
assert reported(ai_explicitly_allowed=True)[1]["aiRule"] == "可以（明确允许）"
for allowed in (False, True):
    item = reported(ai_explicitly_forbidden=True, ai_explicitly_allowed=allowed, ai_evidence="不得使用生成式 AI")[1]
    assert item["aiAllowed"] is False and item["aiRule"] == "不允许（不得使用生成式 AI）"

try:
    agent.Extraction(**base, fee_status="probably_free")
except ValidationError:
    pass
else:
    raise AssertionError("Fee classification is a closed enum")

assert reported(eligibility_status="ineligible")[0] == "ignored"
assert reported(deadline="2020-01-01", deadline_status="exact")[0] == "ignored"
assert "参赛资格待确认" in reported(eligibility_status="unclear")[1]["pendingReason"]
assert "截止时间待确认" in reported(deadline_status="unclear")[1]["pendingReason"]

prompts = []
theme_task = "\n".join([
    "背景介绍：围绕品牌传承开展视觉设计。",
    "命题一：山水之间（海报赛道）。以当地风景为主题，制作 1—4 幅 A3 海报。",
    "命题二：城市记忆（包装赛道）。以街巷文化为主题，提交包装展开图或品牌 VI 手册二选一。",
    "共通要求：参赛作品须为原创，各命题独立参赛。",
])
submission_format = "\n".join([
    "AIGC 品牌短片（必交）：1—3 分钟，MP4，1080P，16:9，H.264。",
    "AIGC 视觉海报（必交）：1—4 幅，A3 以上，JPG，300DPI，每张不超过 5MB。",
    "制作报告（必交）：500 字以内，PDF，不超过 10MB。",
    "宣讲视频（选交）：不超过 3 分钟，MP4，不超过 300MB。",
    "平面赛道：包装展开图或品牌 VI 手册二选一；视频赛道只交短片。",
    "命题一：山水之间（海报赛道）——海报 1—4 幅，A3，JPG，300DPI。",
    "命题二：城市记忆（包装赛道）——包装展开图或品牌 VI 手册二选一，PDF。",
    "总体要求：文件不得出现作者姓名。",
])
assert "difficulty" not in agent.Extraction.model_json_schema()["properties"]


def model_reply(messages):
    prompts.append(messages[1].content[0]["text"])
    return json.dumps({**base, "fee": "免费参赛", "fee_status": "free", "theme_task": theme_task, "submission_format": submission_format,
        "directions": [{**base, "title": "原文方向", "source_heading": "原文方向", "independence": "confirmed", "theme_task": theme_task, "submission_format": submission_format, "evidence": [{"url": candidate["sourceUrl"], "quote": theme_task}], "work_items": [work("海报", quote=theme_task).model_dump()]}]})


extracted = agent.extract(RunnableLambda(model_reply), candidate, [{"url": candidate["sourceUrl"], "text": theme_task, "binary": "", "kind": "html"}], "test-only")
assert extracted.fee_status == "free"
for instruction in ("完整盘点全部投稿组别与方向", "每个标签必须有实际创作任务依据", "配套材料", "字体转曲", "不能拆成独立方向"):
    assert instruction in prompts[0], instruction
assert "work_items" in prompts[0] and "配图冒充主体视觉任务" in prompts[0]
assert "graphic_status" not in prompts[0] and "同一次整理" in prompts[0]
assert "没有提到收费" in prompts[0] and "可选证书/培训费用和差旅费用" in prompts[0]
assert "低/中/高" not in prompts[0] and "difficulty" not in prompts[0]
for instruction in ("不得判断制作难度或工作量等级", "一项一行", "仅在官方明确说明时", "二选一", "不得改成全部必交", "总体要求另起一行", "未公布的细节不编造"):
    assert instruction in prompts[0], instruction
for instruction in ("每个主题、命题或任务独立一段", "保留原编号、命题名称与所属赛道", "创作内容和成品要求放在同段", "背景介绍与共通要求各自独立一段", "保留原标题或编号及归属", "不得把不同命题的材料合并为共同必交内容", "只使用纯文本和换行", "不输出 Markdown 或 HTML"):
    assert instruction in prompts[0], instruction
_, item = agent.report_from(candidate, extracted, [], [])
assert item["themeTask"] == theme_task, "Preserve separate prompts, original numbering, track ownership and shared requirements"
assert item["submissionFormat"] == submission_format, "Preserve lines, quantities, specifications and submission conditions unchanged"
assert "difficulty" not in item
assert reported()[1]["submissionFormat"] == "未公布"

with tempfile.TemporaryDirectory(prefix="competition-rules-") as directory:
    path = Path(directory) / "report.json"
    report = agent.load_report(path)
    p0, p1 = "中国国际大学生创新大赛", "用户认定的全国海报设计竞赛"
    report["items"] = [{**reported(fee="免费参赛", fee_status="free")[1], "title": p0}]
    report["pending"] = [{**reported(eligibility_status="unclear")[1], "id": "2", "sourceUrl": candidate["sourceUrl"].replace("1.html", "2.html"), "title": p1}]
    # A stored record remains intact; no migration or deletion is needed to add extraction fields.
    old = {**reported()[1], "id": "3", "title": "历史普通海报竞赛", "sourceUrl": candidate["sourceUrl"].replace("1.html", "3.html")}
    for key in ("feeStatus", "aiAllowed", "graphicStatus"):
        old.pop(key, None)
    report["items"].append(old)
    agent.save_report(path, report)
    request = {"action": "importRecognition", "provider": "test-only", "pdfBase64": base64.b64encode(b"%PDF-test-only").decode()}
    with patch.object(agent, "competition_model", return_value=(object(), "test-only")), patch.object(agent, "extract_recognized_competitions", return_value=[p0, p1, p1]), patch.dict(agent.os.environ, {"COMPETITION_REPORT_FILE": str(path)}), patch.object(agent.sys, "stdin", io.StringIO(json.dumps(request))), redirect_stdout(io.StringIO()):
        agent.main()
    loaded = agent.load_report(path)
    assert loaded["recognizedNames"] == [p0, p1]
    assert loaded["items"][0]["priority"] == "a_class" and loaded["items"][0]["recognized"] is True
    assert loaded["pending"][0]["priority"] == "recognized" and loaded["pending"][0]["recognized"] is True
    assert loaded["items"][1] == {**old, "recognized": False}, "Existing extracted evidence is retained unchanged"
    agent.save_report(path, loaded)
    assert agent.load_report(path) == loaded, "Uploaded recognition remains machine-level across reloads/conversations"
    old["designTypes"] = []
    old.update(title="IP角色设计征集", themeTask="创作IP角色与条漫。", track="字体", submissionFormat="文字须转曲或嵌入字体")
    loaded["items"] = [old]
    agent.save_report(path, loaded)
    repaired = agent.load_report(path)["items"][0]
    assert repaired["designTypes"] == ["IP/吉祥物", "漫画"], "Fallback never feeds stale tags or submission formats back into classification"
    stored = {**reported(title="文创设计赛道", theme_task="主题原文", submission_format="提交原文")[1], "graphicStatus": "non_graphic", "pendingReason": "平面赛道待确认"}
    child = {**stored, "id": "1:product", "directionId": "1:product", "competitionId": "1"}
    stored["directions"] = [child]
    loaded["items"] = [stored]
    agent.save_report(path, loaded)
    before = path.read_bytes()
    with patch.object(agent, "competition_model", side_effect=AssertionError("Loading must not call a model")):
        unchanged = agent.load_report(path)
        assert unchanged["items"][0]["graphicStatus"] == unchanged["items"][0]["directions"][0]["graphicStatus"] == "non_graphic"
        assert "workItems" not in unchanged["items"][0] and "creationSupport" not in unchanged["items"][0]
        assert unchanged == agent.load_report(path) and path.read_bytes() == before, "No read-time migration, reclassification or writes"
    for field, invalid in [("creationSupport", {"status": "maybe", "reason": ""}), ("creationSupport", {"status": "supported", "reason": []}), ("workItems", []), ("workItems", [{**work("海报").model_dump(), "kind": "invalid"}])]:
        assert not agent.valid_record({**choices, field: invalid}, True), field
    assert agent.valid_record(choices, True)
    assert not agent.valid_record({**stored, "directions": [], "creationSupport": {"status": "supported", "reason": ""}}, True), "A saved support claim needs its decision facts"

print("Rule checks passed: complete 84-entry P0 catalogue, bounded aliases/series, excluded teacher events, explicit fee states, preserved AI policy, persistent P0/P1 recognition and factual submission lists without difficulty ratings.")
