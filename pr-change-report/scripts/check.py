#!/usr/bin/env python3
"""usage: check.py <report.json> [--out report.html] [--comment comment.md] [--meta k=v ...]

--meta 키: repo(owner/repo), pr, pr_title, head, base_ref, date, team(머리말 이름, 없으면 repo 의 저장소 이름).

report.json 의 구조와 문구를 검사한다. 문제가 있으면 목록을 출력하고 1 로 끝난다.
문제가 없고 --out 이 있으면 HTML 한 파일을 만든다. --comment 는 PR 코멘트 본문이다.
표준 라이브러리만 쓴다. 블록 형식은 prompt.md 의 「블록」 절과 맞춘다.
"""

import html
import json
import re
import sys

# 길이 한도. 리포트가 길어지면 읽지 않는다
MAX_SECTIONS = 6
MAX_BLOCKS = 4
MAX_TEXT = 200  # text·callout 블록 한 개의 글자 수
MAX_ITEM = 120  # bullets 항목, flow 설명
MAX_CELL = 110  # 표 칸
MAX_PROSE = 2200  # 코드·표를 뺀 글 전체
MAX_HEADING = 22
CODE_COLS = 84
PAIR_COLS = 62

# 한 번만 나와도 고친다
BANNED = [
    (r"[—–]|\s--\s", "줄표를 쓰지 않습니다. 마침표나 쉼표로 나눕니다"),
    (
        r"정리했습니다|살펴보|알아보겠|짚어보|소개합니다",
        "무엇을 할지 예고하지 말고 내용을 바로 씁니다",
    ),
    (
        r"결론적으로|요컨대|종합하면|궁극적으로|한마디로",
        "결론 신호어를 빼고 사실만 씁니다",
    ),
    (
        r"핵심은|본질적으로|진짜 문제|중요한 것은|중요한 점은|주목할|관건은",
        "강조 수사를 빼고 사실만 씁니다",
    ),
    (r"것이 아니라|뿐만 아니라|뿐 아니라", "반전 구문 대신 바뀐 것을 바로 씁니다"),
    (
        r"다양한|획기적|혁신적|극대화|원활|시너지|전반적|심층|효과적으로|효율적으로|대폭|크게 (개선|향상|줄)",
        "꾸미는 말 대신 숫자나 사실을 씁니다",
    ),
    (r"이를 통해|이러한|나아가|아울러|이와 같이|이로써", "문두 연결 표현을 뺍니다"),
    (
        r"할 수 있게 되었|하게 되었습니다|하게 됩니다|역할을 (수행|합니다)|자리잡",
        "서술어를 줄입니다 (예: 됐습니다, 합니다)",
    ),
    (
        r"인 셈입니다|하는 이유입니다|직결|의미합니다|보여줍니다|말해줍니다",
        "결산하는 문장을 빼고 원인과 결과를 순서대로 씁니다",
    ),
    (
        r"왼쪽이|오른쪽이|아래 (표|그림|코드|다이어그램)[은는]|위 (표|그림)[은는]|다음은 ",
        "그림·표를 설명하는 문장은 caption 에 짧게 씁니다",
    ),
    (
        r"붙잡|주범|발목|두뇌|심장|교통정리|마법|날개|걸림돌|숨통",
        "비유 대신 실제로 일어난 일을 씁니다",
    ),
    (r"\*\*|__", "굵은 글씨를 쓰지 않습니다"),
    (r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", "이모지를 쓰지 않습니다"),
    (r"에 있어서|에 의해|함으로써|하는 것이 가능", "번역투를 풀어 씁니다"),
]
HEADING_BAD = [
    (
        r"(니다|한다|된다|있다|없다|했다|됐다|이다|어요|아요|세요|까)[.?!]?$",
        "제목은 명사로 끝냅니다 (예: 쿼리 비교)",
    ),
    (r"[,:·]|에서 .*(으로|로)$", "제목에 쉼표·쌍점을 넣지 않고 한 가지만 씁니다"),
    (
        r"^(들어가며|마치며|개요|소개|결론|요약|배경|정리)$",
        "틀만 있는 제목을 쓰지 않습니다. 그 절의 내용을 이름으로 씁니다",
    ),
]
TOKEN = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-ant-[A-Za-z0-9_-]{16,}|x-access-token:[^@\s]*"
)

C = {
    "p60": "#5e51ff",
    "p10": "#ecefff",
    "p20": "#dce2ff",
    "g5": "#fafafa",
    "g10": "#f6f6f6",
    "g15": "#f0f0f0",
    "g30": "#e0e0e0",
    "g50": "#bbbbbb",
    "g70": "#707070",
    "g80": "#424242",
    "g90": "#242424",
    "r70": "#c4442b",
    "r10": "#fdeeea",
    "o10": "#fff3e5",
    "o100": "#8a4b00",
}
FONT = (
    "Pretendard Variable, Pretendard, -apple-system, 'Apple SD Gothic Neo', sans-serif"
)
MONO = "'JetBrains Mono', Menlo, Consolas, monospace"


def esc(value):
    return html.escape(str(value), quote=True)


def inline(text):
    """`코드` 만 꾸민다."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(text))


def cols(line):
    return sum(2 if ord(ch) > 0x1100 else 1 for ch in line)


# ---------------- 검사 ----------------
class Problems(list):
    def add(self, where, message):
        self.append(f"{where}: {message}")


def check_prose(problems, where, text, limit):
    if not isinstance(text, str) or not text.strip():
        problems.add(where, "비어 있습니다")
        return 0
    if len(text) > limit:
        problems.add(where, f"{len(text)}자입니다. {limit}자 안으로 줄입니다")
    for pattern, message in BANNED:
        found = re.search(pattern, text)
        if found:
            problems.add(where, f"「{found.group(0).strip()}」 {message}")
    sentences = [s for s in re.split(r"(?<=[.?!])\s+", text.strip()) if s]
    if len(sentences) > 3:
        problems.add(
            where,
            f"{len(sentences)}문장입니다. 3문장 안으로 줄이거나 bullets·table 로 바꿉니다",
        )
    short = 0
    for sentence in sentences:
        short = short + 1 if len(sentence) <= 14 else 0
        if short >= 3:
            problems.add(where, "짧은 단정문이 세 번 이어집니다. 한 문장으로 잇습니다")
            break
    return len(text)


def check_heading(problems, where, text, limit=MAX_HEADING):
    if not isinstance(text, str) or not text.strip():
        problems.add(where, "비어 있습니다")
        return
    if len(text) > limit:
        problems.add(where, f"{len(text)}자입니다. {limit}자 안으로 줄입니다")
    for pattern, message in HEADING_BAD:
        if re.search(pattern, text.strip()):
            problems.add(where, f"「{text}」 {message}")
    for pattern, message in BANNED:
        if re.search(pattern, text):
            problems.add(where, f"「{text}」 {message}")


def check_code(problems, where, code, limit):
    if not isinstance(code, str) or not code.strip():
        problems.add(where, "비어 있습니다")
        return
    lines = code.split("\n")
    if len(lines) > 40:
        problems.add(where, f"{len(lines)}줄입니다. 바뀐 부분만 40줄 안으로 남깁니다")
    for line in lines:
        width = cols(line.lstrip("!"))
        if width > limit:
            problems.add(
                where,
                f"{width}칸인 줄이 있습니다. {limit}칸 안으로 줄바꿈합니다: {line[:40]}",
            )
            break


def check_block(problems, where, block):
    """글 길이(코드·표 제외)를 돌려준다."""
    kind = block.get("type") if isinstance(block, dict) else None
    prose = 0
    caption = block.get("caption") if isinstance(block, dict) else None
    if caption:
        prose += check_prose(problems, f"{where}.caption", caption, MAX_ITEM)
    if kind in ("text", "callout"):
        prose += check_prose(problems, where, block.get("text"), MAX_TEXT)
    elif kind == "bullets":
        items = block.get("items") or []
        if not 1 <= len(items) <= 6:
            problems.add(where, "items 는 1~6개입니다")
        for i, item in enumerate(items):
            if item.get("label"):
                check_heading(problems, f"{where}.items[{i}].label", item["label"], 16)
            prose += check_prose(
                problems, f"{where}.items[{i}].text", item.get("text"), MAX_ITEM
            )
    elif kind == "table":
        headers, rows = block.get("headers") or [], block.get("rows") or []
        if not headers or not rows:
            problems.add(where, "headers 와 rows 가 필요합니다")
        if len(rows) > 10:
            problems.add(where, f"{len(rows)}행입니다. 10행 안으로 줄입니다")
        for r, row in enumerate(rows):
            if len(row) != len(headers):
                problems.add(f"{where}.rows[{r}]", "칸 수가 headers 와 다릅니다")
            for cell in row:
                check_prose(problems, f"{where}.rows[{r}]", str(cell), MAX_CELL)
    elif kind == "compare":
        if block.get("lang") not in ("python", "sql", "text"):
            problems.add(where, "lang 은 python·sql·text 중 하나입니다")
        if block.get("lang") == "sql" and block.get("sql_source") not in (
            "derived",
            "captured",
        ):
            problems.add(
                where,
                "SQL 비교에는 sql_source 가 필요합니다 (derived: 코드에서 옮김, captured: 실행해 캡처)",
            )
        for side in ("before", "after"):
            part = block.get(side) or {}
            check_code(problems, f"{where}.{side}.code", part.get("code"), PAIR_COLS)
            if str(part.get("title", "")).strip() in (
                "이전",
                "이후",
                "수정 전",
                "수정 후",
            ):
                problems.add(
                    f"{where}.{side}.title",
                    "이전·이후 표시는 자동으로 붙습니다. title 은 그 코드의 이름을 쓰거나 비웁니다",
                )
    elif kind == "code":
        check_code(problems, f"{where}.code", block.get("code"), CODE_COLS)
    elif kind == "flow":
        steps = block.get("steps") or []
        if not 2 <= len(steps) <= 6:
            problems.add(where, "steps 는 2~6개입니다")
        for i, step in enumerate(steps):
            at = f"{where}.steps[{i}]"
            check_heading(problems, f"{at}.title", step.get("title"), 16)
            lines = step.get("lines") or []
            if not 1 <= len(lines) <= 2:
                problems.add(at, "lines 는 그 단계가 하는 일 1~2줄입니다")
            for line in lines:
                if cols(str(line)) > 32:
                    problems.add(
                        at, f"「{line}」 한 줄은 32칸(한글 16자) 안으로 줄입니다"
                    )
                prose += check_prose(problems, f"{at}.lines", str(line), 32)
    elif kind == "sequence":
        diagrams = block.get("diagrams") or []
        if not 1 <= len(diagrams) <= 2:
            problems.add(where, "diagrams 는 1개(단독) 또는 2개(이전·이후)입니다")
        for d, diagram in enumerate(diagrams):
            lanes = [lane.get("key") for lane in diagram.get("lanes") or []]
            for lane in diagram.get("lanes") or []:
                if (
                    cols(str(lane.get("label", ""))) > 16
                    or cols(str(lane.get("sub", ""))) > 18
                ):
                    problems.add(
                        f"{where}.diagrams[{d}].lanes",
                        f"「{lane.get('label')}」 label 은 16칸, sub 는 18칸 안으로 줄입니다 (sub 는 파일 이름만)",
                    )
            if str(diagram.get("title", "")).strip() in (
                "이전",
                "이후",
                "수정 전",
                "수정 후",
            ):
                problems.add(
                    f"{where}.diagrams[{d}].title",
                    "이전·이후 표시는 자동으로 붙습니다. title 은 그 방식의 이름을 쓰거나 비웁니다",
                )
            if not 2 <= len(lanes) <= 4:
                problems.add(f"{where}.diagrams[{d}]", "lanes 는 2~4개입니다")
            depth = 0
            steps = diagram.get("steps") or []
            if len(steps) > 14:
                problems.add(
                    f"{where}.diagrams[{d}]",
                    f"steps 가 {len(steps)}개입니다. 14개 안으로 줄입니다",
                )
            for s, step in enumerate(steps):
                at = f"{where}.diagrams[{d}].steps[{s}]"
                step_kind = step.get("kind")
                if step_kind == "msg":
                    if (
                        step.get("from") not in lanes
                        or step.get("to") not in lanes
                        or step.get("from") == step.get("to")
                    ):
                        problems.add(at, "from·to 는 서로 다른 lanes 의 key 입니다")
                elif step_kind == "self":
                    if step.get("at") not in lanes:
                        problems.add(at, "at 은 lanes 의 key 입니다")
                elif step_kind == "loop_start":
                    depth += 1
                elif step_kind == "loop_end":
                    depth -= 1
                else:
                    problems.add(
                        at, "kind 는 msg·self·loop_start·loop_end 중 하나입니다"
                    )
                if (
                    step_kind in ("msg", "self", "loop_start")
                    and len(str(step.get("label", ""))) > 26
                ):
                    problems.add(at, "label 은 26자 안으로 줄입니다")
                if not step.get("label") and step_kind != "loop_end":
                    problems.add(at, "label 이 필요합니다")
            if depth != 0:
                problems.add(
                    f"{where}.diagrams[{d}]",
                    "loop_start 와 loop_end 의 짝이 맞지 않습니다",
                )
    elif kind == "tables":
        tables = block.get("tables") or []
        if not 1 <= len(tables) <= 14:
            problems.add(where, "tables 는 1~14개입니다")
        fields_by_key = {}
        for t, table in enumerate(tables):
            at = f"{where}.tables[{t}]"
            if (
                not table.get("key")
                or not table.get("model")
                or not table.get("fields")
            ):
                problems.add(at, "key, model, fields 가 필요합니다")
            if table.get("key") in fields_by_key:
                problems.add(at, "key 가 겹칩니다")
            fields = table.get("fields") or []
            fields_by_key[table.get("key")] = {field.get("name") for field in fields}
            if len(fields) > 8:
                problems.add(
                    at,
                    "fields 는 이 변경이 읽고 쓰는 것과 관계에 쓰는 것만 8개 안으로 남깁니다",
                )
            for field in fields:
                if field.get("badge") not in (None, "", "PK", "FK", "IDX"):
                    problems.add(at, "badge 는 PK·FK·IDX 중 하나입니다")
                if (
                    cols(str(field.get("name", ""))) > 30
                    or cols(str(field.get("note", ""))) > 36
                ):
                    problems.add(
                        at,
                        f"「{field.get('name')}」 name 은 30칸, note 는 36칸 안으로 줄입니다",
                    )
            for line in table.get("use") or []:
                prose += check_prose(problems, f"{at}.use", line, 40)
                if cols(line) > 40:
                    problems.add(
                        f"{at}.use",
                        f"「{line}」 한 줄은 40칸(한글 20자) 안으로 줄입니다",
                    )
        relations = block.get("relations") or []
        if len(tables) >= 2 and not relations:
            problems.add(
                where,
                "relations 가 필요합니다. 표 사이의 FK·JSON 키·복사 관계를 선으로 그립니다",
            )
        for r, relation in enumerate(relations):
            at = f"{where}.relations[{r}]"
            if relation.get("kind") not in ("fk", "json", "copy"):
                problems.add(at, "kind 는 fk·json·copy 중 하나입니다")
            for side, name in (("from", "field"), ("to", "to_field")):
                key = relation.get(side)
                if key not in fields_by_key:
                    problems.add(at, f"{side} 는 tables 의 key 입니다")
                elif relation.get(name) and relation[name] not in fields_by_key[key]:
                    problems.add(
                        at, f"{name} 「{relation[name]}」 가 그 표의 fields 에 없습니다"
                    )
            if relation.get("from") == relation.get("to"):
                problems.add(at, "from 과 to 가 같습니다")
    elif kind == "bars":
        items = block.get("items") or []
        if not 1 <= len(items) <= 4:
            problems.add(where, "items 는 1~4개입니다")
        if not block.get("source"):
            problems.add(
                where,
                "source 가 필요합니다 (PR 본문이나 테스트의 어디에서 온 숫자인지)",
            )
        for i, item in enumerate(items):
            for side in ("before", "after"):
                part = item.get(side) or {}
                if not isinstance(part.get("value"), (int, float)) or not part.get(
                    "text"
                ):
                    problems.add(
                        f"{where}.items[{i}].{side}",
                        "value(숫자)와 text(표시할 글자)가 필요합니다",
                    )
    else:
        problems.add(where, f"모르는 type 입니다: {kind}")
    return prose


def check(report):
    problems = Problems()
    if not isinstance(report, dict):
        problems.add("report", "객체가 아닙니다")
        return problems
    check_heading(problems, "title", report.get("title"), 30)
    prose = check_prose(problems, "lead", report.get("lead"), 140)
    kpis = report.get("kpis") or []
    if len(kpis) > 3:
        problems.add("kpis", "3개까지입니다")
    for i, kpi in enumerate(kpis):
        if not kpi.get("label") or not kpi.get("value"):
            problems.add(f"kpis[{i}]", "label 과 value 가 필요합니다")
    sections = report.get("sections") or []
    if not 1 <= len(sections) <= MAX_SECTIONS:
        problems.add("sections", f"1~{MAX_SECTIONS}개입니다")
    for s, section in enumerate(sections):
        where = f"sections[{s}]"
        check_heading(problems, f"{where}.heading", section.get("heading"))
        blocks = section.get("blocks") or []
        if not 1 <= len(blocks) <= MAX_BLOCKS:
            problems.add(where, f"blocks 는 1~{MAX_BLOCKS}개입니다")
        if blocks and all(block.get("type") == "text" for block in blocks):
            problems.add(
                where,
                "글만 있는 절입니다. 표·비교·그림 가운데 하나로 보여 주거나 절을 뺍니다",
            )
        for b, block in enumerate(blocks):
            prose += check_block(
                problems, f"{where}.blocks[{b}]({block.get('type')})", block
            )
    for i, row in enumerate(report.get("sources") or []):
        if not row.get("label") or not row.get("text"):
            problems.add(f"sources[{i}]", "label 과 text 가 필요합니다")
    if prose > MAX_PROSE:
        problems.add(
            "report",
            f"코드·표를 뺀 글이 {prose}자입니다. {MAX_PROSE}자 안으로 줄입니다",
        )
    return problems


# ---------------- 그리기 ----------------
CSS = f"""
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css');
*{{box-sizing:border-box}}
html{{overflow-x:clip}}
body{{margin:0;background:#fff;color:{C['g90']};font-family:{FONT};font-size:16px;line-height:1.75;word-break:keep-all;-webkit-font-smoothing:antialiased}}
.top{{border-bottom:1px solid {C['g15']}}}
.top .in{{max-width:760px;margin:0 auto;padding:12px 24px;font-size:14px;color:{C['g70']}}}
.top b{{color:{C['p60']};font-weight:600}}
article{{max-width:760px;margin:0 auto;padding:40px 24px 32px}}
h1{{font-size:30px;line-height:1.35;font-weight:600;margin:0 0 10px;letter-spacing:-.01em}}
.lead{{font-size:17px;color:{C['g80']};margin:0 0 22px;max-width:680px}}
.kpis{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:0 0 8px}}
.kpis div{{border:1px solid {C['g30']};border-radius:12px;padding:14px 16px}}
.kpis span{{display:block;font-size:13px;color:{C['g70']};line-height:1.5}}
.kpis b{{display:block;font-size:21px;font-weight:600;margin-top:4px;line-height:1.3}}
.kpis small{{display:block;font-size:12.5px;color:{C['g70']};margin-top:2px}}
h2{{font-size:22px;line-height:1.4;font-weight:600;margin:44px 0 12px}}
p{{margin:0 0 14px;max-width:680px}}
figure{{margin:16px 0 22px}}
figure.box{{padding:18px;border:1px solid {C['g15']};border-radius:12px}}
figcaption,.cap{{font-size:13px;color:{C['g70']};margin:8px 0 0;line-height:1.6}}
.snip{{background:#1f2130;border-radius:10px;overflow:hidden}}
.snip-head{{display:flex;align-items:center;gap:8px;padding:7px 12px;background:#2a2c3f;font-size:12.5px;color:#c9cbe0;min-height:36px}}
.snip-head .lang{{font-family:{MONO};font-weight:600;font-size:11.5px;color:#9da0bd}}
.snip-head .name{{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.snip-head .name code{{background:none;border:0;color:#e6e6f0;padding:0}}
.snip-head .tail{{margin-left:auto;display:flex;align-items:center;gap:10px;flex:none}}
.snip-head .copy{{font:inherit;font-size:11.5px;color:#9da0bd;background:none;border:1px solid #454867;border-radius:5px;padding:1px 8px;cursor:pointer}}
.snip-head .copy:hover{{color:#fff;border-color:#8b8fa8}}
pre{{color:#e6e6f0;padding:10px 0;overflow-x:auto;font-size:12.5px;line-height:1.65;margin:0;font-family:{MONO}}}
pre .l{{display:block;white-space:pre;padding-right:14px;min-width:max-content}}
pre .l i{{font-style:normal;display:inline-block;user-select:none}}
pre .no{{width:34px;text-align:right;color:#5d6080}}
pre .sg{{width:22px;text-align:center;font-weight:700}}
pre .l.del{{background:rgba(229,83,75,.2)}} pre .l.del .sg{{color:#ff8f85}}
pre .l.add{{background:rgba(63,185,110,.2)}} pre .l.add .sg{{color:#7ee2a0}}
pre .l.hl{{background:rgba(114,115,255,.28)}}
pre .tk{{color:#c4a7ff}} pre .ts{{color:#a8dba8}} pre .tn{{color:#f2b880}} pre .tc{{color:#8b8fa8}} pre .tf{{color:#8fc7ff}} pre .td{{color:#f2b880}}
code{{font-family:{MONO};font-size:.86em;background:{C['g10']};border:1px solid {C['g15']};border-radius:4px;padding:1px 5px}}
table{{width:100%;border-collapse:collapse;font-size:14.5px;margin:0}}
th{{background:{C['g5']};color:{C['g70']};font-weight:500;font-size:13px;text-align:left;padding:9px 12px;border-bottom:1px solid {C['g30']}}}
td{{padding:10px 12px;border-bottom:1px solid {C['g15']};vertical-align:top;line-height:1.6}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
tr.pick td{{background:{C['p10']}}}
.chip{{display:inline-block;font-size:12px;font-weight:600;padding:2px 9px;border-radius:999px;line-height:1.6}}
.chip.old{{background:{C['g10']};color:{C['g80']}}}
.chip.new{{background:{C['p10']};color:{C['p60']}}}
.chip.est{{background:{C['o10']};color:{C['o100']}}}
.wide{{width:min(1120px,calc(100vw - 32px));position:relative;left:50%;transform:translateX(-50%)}}
.pair{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;align-items:start}}
td code,.foot code{{word-break:break-all}}
figure.scroll{{overflow-x:auto}}
.pair>div{{min-width:0}}
.pair h4{{margin:0 0 8px;font-size:13.5px;font-weight:500;color:{C['g80']};display:flex;gap:8px;align-items:center}}
ul.kv{{list-style:none;padding:0;margin:0 0 14px;border-top:1px solid {C['g15']}}}
ul.kv li{{display:grid;grid-template-columns:132px 1fr;gap:14px;padding:9px 0;border-bottom:1px solid {C['g15']};font-size:15px}}
ul.kv li b{{font-weight:600;font-size:14px}}
ul.kv li.solo{{grid-template-columns:1fr}}
.flowfig svg{{min-width:560px}}
.erd-legend{{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12.5px;color:{C['g80']};margin:0 0 10px}}
.erd-legend i{{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;vertical-align:-1px}}
.erd-legend b{{display:inline-block;width:26px;height:0;margin-right:6px;vertical-align:4px}}
.erd-scroll{{overflow-x:auto;border:1px solid {C['g15']};border-radius:12px;padding:14px}}
.bars .row{{display:grid;grid-template-columns:150px 1fr;gap:14px;align-items:center;padding:8px 0;border-bottom:1px solid {C['g15']}}}
.bars .name b{{font-size:14.5px;font-weight:600}} .bars .name span{{display:block;font-size:12px;color:{C['g70']}}}
.bars .track{{padding-right:96px}}
.bar{{height:13px;border-radius:3px;position:relative;margin:4px 0;min-width:2px}}
.bar em{{position:absolute;left:calc(100% + 8px);top:-5px;font-style:normal;font-size:12.5px;white-space:nowrap;font-variant-numeric:tabular-nums}}
.bar.old{{background:{C['g50']}}} .bar.new{{background:{C['p60']}}} .bar.new em{{color:{C['p60']};font-weight:600}}
.callout{{border-left:3px solid {C['p60']};background:{C['p10']};border-radius:0 8px 8px 0;padding:12px 16px;margin:0 0 14px;font-size:15px}}
.callout.warn{{border-color:#e59333;background:{C['o10']}}}
.foot{{max-width:760px;margin:24px auto 0;padding:22px 24px 48px;border-top:1px solid {C['g15']}}}
.foot h4{{font-size:13.5px;font-weight:600;margin:0 0 10px;color:{C['g80']}}}
.foot dl{{display:grid;grid-template-columns:110px 1fr;gap:6px 16px;margin:0;font-size:13px;line-height:1.6}}
.foot dt{{color:{C['g70']}}} .foot dd{{margin:0;color:{C['g80']};word-break:break-all}}
@media (max-width:900px){{.pair{{grid-template-columns:minmax(0,1fr)}}}}
@media (max-width:640px){{.kpis{{grid-template-columns:1fr}} h1{{font-size:25px}} .bars .row{{grid-template-columns:1fr}} ul.kv li{{grid-template-columns:1fr;gap:2px}}}}
"""


PY_WORDS = (
    "def class return if elif else for while in not and or is None True False with as try except finally "
    "raise import from lambda yield pass break continue assert async await self"
)
SQL_WORDS = (
    "select from where and or not in is null as on join left right inner outer full cross group by order "
    "having limit offset insert into values update set delete distinct union all exists between like case "
    "when then else end asc desc for filter over partition returning with create index concurrently using "
    "begin commit rollback explain analyze count sum avg min max coalesce true false"
)
TOKEN_RE = {
    "python": re.compile(
        r"(?P<s>[fbr]?\"(?:\\.|[^\"\\])*\"|[fbr]?'(?:\\.|[^'\\])*')"
        r"|(?P<c>#.*$)|(?P<n>\b\d[\d_.]*\b)|(?P<d>@\w+)|(?P<w>\b[A-Za-z_]\w*\b)"
    ),
    "sql": re.compile(
        r"(?P<s>'(?:''|[^'])*')|(?P<c>--.*$)|(?P<n>\b\d[\d.]*\b|%s)|(?P<w>\b[A-Za-z_]\w*\b)"
    ),
}
WORDS = {"python": set(PY_WORDS.split()), "sql": set(SQL_WORDS.split())}


def highlight(line, lang):
    """키워드·문자열·숫자·주석에 색을 입힌다. 모르는 언어는 그대로 둔다."""
    pattern = TOKEN_RE.get(lang)
    if not pattern:
        return esc(line)
    out, last = [], 0
    for found in pattern.finditer(line):
        out.append(esc(line[last : found.start()]))
        last = found.end()
        kind, text = found.lastgroup, found.group(0)
        if kind == "w":
            word = text.lower() if lang == "sql" else text
            if word in WORDS[lang]:
                kind = "k"
            elif lang == "python" and line[found.end() : found.end() + 1] == "(":
                kind = "f"
            else:
                kind = None
        out.append(f'<span class="t{kind}">{esc(text)}</span>' if kind else esc(text))
    out.append(esc(line[last:]))
    return "".join(out)


def render_code(code, lang="python", side=None, title=""):
    """스니펫 한 개. '!' 로 시작하는 줄은 이전 쪽에서 -, 이후 쪽에서 +, 단독 코드에서 강조로 그린다."""
    sign, mark = {"before": ("-", "del"), "after": ("+", "add")}.get(side, ("", "hl"))
    lines = []
    for number, line in enumerate(code.strip("\n").split("\n"), 1):
        changed = line.startswith("!")
        if changed:
            line = line[1:]
        lines.append(
            f'<span class="l{" " + mark if changed else ""}"><i class="no">{number}</i>'
            f'<i class="sg">{sign if changed else ""}</i><span class="tx">{highlight(line, lang) or " "}</span></span>'
        )
    label = {"python": "Python", "sql": "SQL"}.get(lang, "")
    head = (chip(side) if side else "") + (
        f'<span class="name">{inline(title)}</span>' if title else ""
    )
    tail = (f'<b class="lang">{label}</b>' if label else "") + (
        '<button type="button" class="copy">복사</button>'
    )
    return (
        f'<div class="snip"><div class="snip-head">{head}<span class="tail">{tail}</span></div>'
        f'<pre>{"".join(lines)}</pre></div>'
    )


COPY_JS = """<script>
document.addEventListener('click', function (event) {
  var button = event.target.closest('.snip .copy');
  if (!button) return;
  var lines = button.closest('.snip').querySelectorAll('.tx');
  var text = Array.prototype.map.call(lines, function (line) { return line.textContent; }).join(String.fromCharCode(10));
  navigator.clipboard.writeText(text).then(function () {
    button.textContent = '복사됨';
    setTimeout(function () { button.textContent = '복사'; }, 1200);
  });
});
</script>"""


def render_sequence(diagram, width):
    lanes = diagram["lanes"]
    margin = 76
    span = (width - 2 * margin) / (len(lanes) - 1)
    xs = {lane["key"]: margin + i * span for i, lane in enumerate(lanes)}
    top, head = 8, 48
    box = min(120, span - 10)
    small = box < 110
    y = top + head + 28
    parts, loops = [], []
    for step in diagram["steps"]:
        kind = step["kind"]
        if kind == "loop_start":
            loops.append((y - 6, step["label"]))
            y += 46
        elif kind == "loop_end":
            y0, label = loops.pop()
            parts.append(("loop", y0, y, label))
            y += 30
        elif kind == "msg":
            parts.append(("msg", y, step))
            y += 52 if step.get("note") else 38
        elif kind == "self":
            parts.append(("self", y, step))
            y += 56 if step.get("note") else 44
    height = y + 4
    svg = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" style="font-family:{FONT};max-width:{width}px">',
        '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{C["g80"]}"/></marker>'
        '<marker id="ahp" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{C["p60"]}"/></marker></defs>',
    ]
    for part in parts:
        if part[0] == "loop":
            _, y0, y1, label = part
            svg.append(
                f'<rect x="10" y="{y0}" width="{width - 20}" height="{y1 - y0}" rx="8" fill="{C["r10"]}" '
                f'fill-opacity=".55" stroke="{C["r70"]}" stroke-opacity=".45" stroke-dasharray="4 3"/>'
                f'<rect x="10" y="{y0}" width="{cols(label) * 6.6 + 22}" height="22" rx="8" fill="{C["r70"]}"/>'
                f'<text x="21" y="{y0 + 15.5}" font-size="12" font-weight="600" fill="#fff">{esc(label)}</text>'
            )
    for lane in lanes:
        x = xs[lane["key"]]
        svg.append(
            f'<line x1="{x}" y1="{top + head}" x2="{x}" y2="{height - 4}" stroke="{C["g30"]}" stroke-dasharray="3 4"/>'
            f'<rect x="{x - box / 2}" y="{top}" width="{box}" height="{head}" rx="8" fill="#fff" stroke="{C["g30"]}"/>'
            f'<text x="{x}" y="{top + 20}" text-anchor="middle" font-size="{12 if small else 13}" font-weight="600" fill="{C["g90"]}">{esc(lane.get("label", ""))}</text>'
            f'<text x="{x}" y="{top + 37}" text-anchor="middle" font-size="{10 if small else 11}" fill="{C["g70"]}">{esc(lane.get("sub", ""))}</text>'
        )
    for part in parts:
        if part[0] == "msg":
            _, y, step = part
            x1, x2 = xs[step["from"]], xs[step["to"]]
            hot = step.get("hot")
            color = C["p60"] if hot else C["g80"]
            dash = ' stroke-dasharray="5 4"' if step.get("ret") else ""
            tip = x2 - 6 if x2 > x1 else x2 + 6
            mid = (x1 + x2) / 2
            svg.append(
                f'<line x1="{x1}" y1="{y}" x2="{tip}" y2="{y}" stroke="{color}" stroke-width="{1.8 if hot else 1.3}"{dash} '
                f'marker-end="url(#{"ahp" if hot else "ah"})"/>'
                f'<text x="{mid}" y="{y - 7}" text-anchor="middle" font-size="12" font-weight="{600 if hot else 500}" '
                f'fill="{color if hot else C["g90"]}">{esc(step["label"])}</text>'
            )
            if step.get("note"):
                svg.append(
                    f'<text x="{mid}" y="{y + 15}" text-anchor="middle" font-size="11" fill="{C["g70"]}">{esc(step["note"])}</text>'
                )
        elif part[0] == "self":
            _, y, step = part
            x = xs[step["at"]]
            # 맨 오른쪽 줄에서는 글자가 잘리지 않게 왼쪽으로 그린다
            left = x + 40 + cols(step["label"]) * 6.4 > width
            sign = -1 if left else 1
            anchor = ' text-anchor="end"' if left else ""
            svg.append(
                f'<path d="M{x},{y - 8} h{sign * 30} v18 h{sign * -24}" fill="none" stroke="{C["p60"]}" stroke-width="1.5" marker-end="url(#ahp)"/>'
                f'<text x="{x + sign * 40}" y="{y + 5}"{anchor} font-size="12" font-weight="600" fill="{C["p60"]}">{esc(step["label"])}</text>'
            )
            if step.get("note"):
                svg.append(
                    f'<text x="{x + sign * 40}" y="{y + 21}"{anchor} font-size="11" fill="{C["g70"]}">{esc(step["note"])}</text>'
                )
    svg.append("</svg>")
    return "".join(svg)


def render_flow(steps):
    """번호 상자를 화살표로 잇는다. 한 줄에 3개, 다음 줄은 반대 방향으로 이어진다."""
    per_row, box_w, box_h, gap_x, gap_y = 3, 222, 84, 21, 34
    width = per_row * box_w + (per_row - 1) * gap_x + 12
    rows = (len(steps) + per_row - 1) // per_row
    height = rows * box_h + (rows - 1) * gap_y + 12
    svg = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" role="img" style="font-family:{FONT};max-width:{width}px">',
        '<defs><marker id="fa" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{C["g70"]}"/></marker></defs>',
    ]
    spots = []
    for i in range(len(steps)):
        row, col = divmod(i, per_row)
        if row % 2:
            col = per_row - 1 - col
        spots.append((6 + col * (box_w + gap_x), 6 + row * (box_h + gap_y)))
    for i, (step, (x, y)) in enumerate(zip(steps, spots)):
        hot = step.get("changed")
        stroke = C["p60"] if hot else C["g50"]
        svg.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="10" fill="{C["p10"] if hot else "#fff"}" stroke="{stroke}"/>'
            f'<circle cx="{x + 20}" cy="{y + 21}" r="10" fill="{stroke}"/>'
            f'<text x="{x + 20}" y="{y + 25}" text-anchor="middle" font-size="11.5" font-weight="700" fill="#fff">{i + 1}</text>'
            f'<text x="{x + 38}" y="{y + 26}" font-size="13.5" font-weight="600" fill="{C["g90"]}">{esc(step["title"])}</text>'
        )
        for n, line in enumerate(step["lines"]):
            svg.append(
                f'<text x="{x + 14}" y="{y + 50 + n * 18}" font-size="12" fill="{C["g80"]}">{esc(str(line).replace("`", ""))}</text>'
            )
        if i + 1 == len(steps):
            continue
        nx, ny = spots[i + 1]
        mid = y + box_h / 2
        if ny != y:
            cx = x + box_w / 2
            line = (cx, y + box_h + 2, cx, ny - 4)
        elif nx > x:
            line = (x + box_w + 2, mid, nx - 4, mid)
        else:
            line = (x - 2, mid, nx + box_w + 4, mid)
        svg.append(
            f'<line x1="{line[0]}" y1="{line[1]}" x2="{line[2]}" y2="{line[3]}" stroke="{C["g70"]}" stroke-width="1.3" marker-end="url(#fa)"/>'
        )
    svg.append("</svg>")
    return "".join(svg)


ERD_GROUP_COLORS = ["#5e51ff", "#c46a0a", "#242424", "#1f7a6d"]  # 묶음이 나온 순서대로
ERD_LINE = {
    "fk": ("#707070", "FK"),
    "json": ("#5e51ff", "JSON 키 (FK 아님)"),
    "copy": ("#c46a0a", "복사"),
}


def text_w(text, size):
    return sum(size * (0.95 if ord(ch) > 0x1100 else 0.6) for ch in str(text))


def erd_layout(tables, relations):
    """표를 (묶음, 열, 줄) 격자에 놓는다.

    FK·복사로 이어진 표끼리 한 묶음이 되고 묶음은 위에서 아래로 쌓인다. JSON 키 관계는 묶음을 잇지 않는다.
    묶음마다 가장 긴 FK 사슬이 첫 줄에 왼쪽에서 오른쪽으로 놓이고, 나머지 표가 빈 칸을 채워 4열 격자가 된다.
    """
    keys = [table["key"] for table in tables]
    parent = {key: key for key in keys}

    def find(key):
        while parent[key] != key:
            key = parent[key]
        return key

    for relation in relations:
        if relation["kind"] != "json":
            parent[find(relation["from"])] = find(relation["to"])
    clusters = []
    for key in keys:
        if find(key) not in clusters:
            clusters.append(find(key))
    depth = {key: 0 for key in keys}
    for _ in keys:
        for relation in relations:
            same = find(relation["from"]) == find(relation["to"])
            if same and depth[relation["from"]] < depth[relation["to"]] + 1:
                depth[relation["from"]] = min(depth[relation["to"]] + 1, 3)
    spots = {}
    for index, root in enumerate(clusters):
        members = [key for key in keys if find(key) == root]
        deepest = max(depth[key] for key in members)
        width = max(deepest + 1, min(4, len(members)))
        # 가장 긴 FK 사슬을 첫 줄에 놓는다
        chain = [next(key for key in members if depth[key] == deepest)]
        while depth[chain[-1]] > 0:
            chain.append(
                next(
                    relation["to"]
                    for relation in relations
                    if relation["from"] == chain[-1]
                    and find(relation["to"]) == root
                    and depth[relation["to"]] == depth[chain[-1]] - 1
                )
            )
        taken = {}
        for key in chain:
            taken[(0, deepest - depth[key])] = key
        # 나머지는 빈 칸 가운데 위쪽 줄, 제 열에 가까운 칸에 채운다
        for key in members:
            if key in chain:
                continue
            ideal = deepest - depth[key]
            placed = {name: col for (_, col), name in taken.items()}
            near = [
                placed[relation[other]]
                for relation in relations
                for side, other in (("from", "to"), ("to", "from"))
                if relation[side] == key and relation[other] in placed
            ]
            last_row = max(row for row, _ in taken) + 1
            cells = [
                (row, col)
                for row in range(last_row + 1)
                for col in range(width)
                if (row, col) not in taken
            ]

            def cost(cell):
                away = sum(abs(cell[1] - col) for col in near)
                return (cell[0] * 10 + abs(cell[1] - ideal) * 3, away, cell[1])

            taken[min(cells, key=cost)] = key
        for (row, col), key in taken.items():
            spots[key] = (index, col, row)
    return spots


def render_erd(tables, relations):
    tw, gap, left = 250, 62, 14
    head, row_h, sub_h, foot_h = 40, 21, 14, 15
    band_gap, cluster_gap = 44, 64
    groups = []
    for table in tables:
        if table.get("group") and table["group"] not in groups:
            groups.append(table["group"])
    spots = erd_layout(tables, relations)
    ncols = max(col for _, col, _ in spots.values()) + 1
    boxes = {}
    for table in tables:
        rows = []
        for field in table["fields"]:
            note = str(field.get("note") or "")
            two = (
                bool(note)
                and 34 + text_w(field["name"], 10.5) + text_w(note, 10) + 12 > tw
            )
            rows.append((field["name"], field.get("badge") or "", note, two))
        use = table.get("use") or []
        box_h = (
            head
            + sum(row_h + (sub_h if r[3] else 0) for r in rows)
            + 10
            + len(use) * foot_h
        )
        cluster, col, row = spots[table["key"]]
        boxes[table["key"]] = dict(
            table=table,
            rows=rows,
            use=use,
            h=box_h,
            col=col,
            band=(cluster, row),
            x=left + col * (tw + gap),
        )
    bands = sorted({box["band"] for box in boxes.values()})
    band_y, y = {}, 30
    for i, band in enumerate(bands):
        if i:
            y += cluster_gap if band[0] != bands[i - 1][0] else band_gap
        band_y[band] = y
        y += max(box["h"] for box in boxes.values() if box["band"] == band)
    height = y + 10
    width = left + ncols * tw + (ncols - 1) * gap + 44
    for box in boxes.values():
        box["y"] = band_y[box["band"]]
        box["field_y"], fy = {}, box["y"] + head
        for name, _, _, two in box["rows"]:
            box["field_y"][name] = fy + row_h / 2
            fy += row_h + (sub_h if two else 0)

    def anchor(key, field):
        box = boxes[key]
        return (
            box["field_y"].get(field, box["y"] + head / 2)
            if field
            else box["y"] + head / 2
        )

    def gutter_x(gutter, lane, count):
        if gutter >= ncols - 1:
            return left + ncols * tw + (ncols - 1) * gap + 12 + lane * 8
        start = left + (gutter + 1) * tw + gutter * gap
        return start + gap * (lane + 1) / (count + 1)

    plans, wanted, channels = [], {}, {}
    for index, relation in enumerate(relations):
        a, b = boxes[relation["from"]], boxes[relation["to"]]
        if b["col"] == a["col"]:
            # 같은 열의 표는 왼쪽 틈으로 잇는다. 첫 열만 오른쪽 틈을 쓴다
            if a["col"] > 0:
                gutters, sx, dx = [a["col"] - 1], a["x"], b["x"]
            else:
                gutters, sx, dx = [a["col"]], a["x"] + tw, b["x"] + tw
        elif b["col"] > a["col"]:
            sx, dx = a["x"] + tw, b["x"]
            gutters = (
                [a["col"]] if b["col"] - a["col"] == 1 else [a["col"], b["col"] - 1]
            )
        else:
            sx, dx = a["x"], b["x"] + tw
            gutters = (
                [b["col"]] if a["col"] - b["col"] == 1 else [a["col"] - 1, b["col"]]
            )
        channel = None
        if len(gutters) == 2:
            # 두 열 이상 건너는 선은 아래쪽 표가 있는 줄 바로 위 빈 띠로 지나간다
            lower = max(a["band"], b["band"])
            channel = (lower, channels.get(lower, 0))
            channels[lower] = channels.get(lower, 0) + 1
        for position, gutter in enumerate(gutters):
            attach = sx if position == 0 and len(gutters) == 2 else dx
            # 왼쪽 표에 닿는 선을 왼쪽 레인에 둬야 마주 보는 화살표의 가로선이 겹치지 않는다
            right_side = attach > left + gutter * (tw + gap) + tw
            wanted.setdefault(gutter, []).append((right_side, index, position))
        plans.append((relation, a, b, gutters, channel, sx, dx))
    lanes, lane_of = {}, {}
    for gutter, entries in wanted.items():
        lanes[gutter] = len(entries)
        for lane, (_, index, position) in enumerate(sorted(entries)):
            lane_of[(index, position)] = lane

    out = [
        f'<svg viewBox="0 0 {width} {height}" width="100%" style="font-family:{FONT};min-width:{min(width, 900)}px" role="img"><defs>'
    ]
    for kind, (color, _) in ERD_LINE.items():
        out.append(
            f'<marker id="erd-{kind}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
        )
    out.append("</defs>")
    edges = []
    for index, (relation, a, b, gutters, channel, sx, dx) in enumerate(plans):
        sy = anchor(relation["from"], relation.get("field"))
        dy = anchor(relation["to"], relation.get("to_field"))
        color = ERD_LINE[relation["kind"]][0]
        dash = "" if relation["kind"] == "fk" else ' stroke-dasharray="5 4"'
        xs = [
            gutter_x(gutter, lane_of[(index, position)], lanes[gutter])
            for position, gutter in enumerate(gutters)
        ]
        if channel is None:
            path = f"M{sx},{sy} H{xs[0]} V{dy} H{dx}"
        else:
            cy = band_y[channel[0]] - 12 - 8 * channel[1]
            path = f"M{sx},{sy} H{xs[0]} V{cy} H{xs[1]} V{dy} H{dx}"
        edges.append(
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.4"{dash} marker-end="url(#erd-{relation["kind"]})"/>'
            f'<circle cx="{sx}" cy="{sy}" r="2.6" fill="{color}"/>'
        )
        if relation.get("label"):
            lx = sx + (gap / 2 if sx < xs[0] else -gap / 2)
            edges.append(
                f'<text x="{lx}" y="{sy - 6}" text-anchor="middle" font-size="10.5" font-weight="600" fill="{color}">{esc(relation["label"])}</text>'
            )
    badge_fill = {
        "PK": (C["o10"], C["o100"]),
        "FK": (C["p10"], C["p60"]),
        "IDX": (C["g15"], C["g80"]),
    }
    for box in boxes.values():
        table, x, y = box["table"], box["x"], box["y"]
        fill = (
            ERD_GROUP_COLORS[groups.index(table["group"]) % 4]
            if table.get("group") in groups
            else C["g80"]
        )
        out.append(
            f'<rect x="{x}" y="{y}" width="{tw}" height="{box["h"]}" rx="8" fill="#fff" stroke="{C["p60"] if table.get("changed") else C["g30"]}"'
            f' stroke-width="{1.6 if table.get("changed") else 1}"/>'
            f'<path d="M{x},{y + 8} a8,8 0 0 1 8,-8 h{tw - 16} a8,8 0 0 1 8,8 v{head - 8} h-{tw} z" fill="{fill}"/>'
            f'<text x="{x + 10}" y="{y + 17}" font-size="12.5" font-weight="700" fill="#fff">{esc(table["model"])}</text>'
        )
        name = str(table.get("table") or "")
        fit = (
            f' textLength="{tw - 20}" lengthAdjust="spacingAndGlyphs"'
            if len(name) * 5.75 > tw - 20
            else ""
        )
        out.append(
            f'<text x="{x + 10}" y="{y + 32}" font-size="9.5" fill="#fff" fill-opacity=".8" font-family="Menlo,monospace"{fit}>{esc(name)}</text>'
        )
        fy = y + head
        for i, (field, badge, note, two) in enumerate(box["rows"]):
            rh = row_h + (sub_h if two else 0)
            if i % 2:
                out.append(
                    f'<rect x="{x + 1}" y="{fy}" width="{tw - 2}" height="{rh}" fill="{C["g5"]}"/>'
                )
            if badge:
                out.append(
                    f'<rect x="{x + 6}" y="{fy + 4.5}" width="24" height="12" rx="3" fill="{badge_fill[badge][0]}"/>'
                    f'<text x="{x + 18}" y="{fy + 13.5}" text-anchor="middle" font-size="8" font-weight="700" fill="{badge_fill[badge][1]}">{badge}</text>'
                )
            out.append(
                f'<text x="{x + 34}" y="{fy + 14.5}" font-size="10.5" fill="{C["g90"]}" font-family="Menlo,monospace">{esc(field)}</text>'
            )
            if note and two:
                out.append(
                    f'<text x="{x + 34}" y="{fy + 14.5 + sub_h}" font-size="10" fill="{C["g70"]}">{esc(note)}</text>'
                )
            elif note:
                out.append(
                    f'<text x="{x + tw - 8}" y="{fy + 14.5}" text-anchor="end" font-size="10" fill="{C["g70"]}">{esc(note)}</text>'
                )
            fy += rh
        if box["use"]:
            out.append(
                f'<line x1="{x}" y1="{fy + 4}" x2="{x + tw}" y2="{fy + 4}" stroke="{C["g15"]}"/>'
            )
        for j, line in enumerate(box["use"]):
            out.append(
                f'<text x="{x + 10}" y="{fy + 17 + j * foot_h}" font-size="10.5" fill="{C["p60"]}">{esc(str(line).replace("`", ""))}</text>'
            )
    out.extend(edges)
    out.append("</svg>")
    legend = [
        f'<span><i style="background:{ERD_GROUP_COLORS[i % 4]}"></i>{esc(group)}</span>'
        for i, group in enumerate(groups)
    ]
    for kind, (color, label) in ERD_LINE.items():
        if any(relation["kind"] == kind for relation in relations):
            style = f"border-top:2px {'solid' if kind == 'fk' else 'dashed'} {color}"
            legend.append(f'<span><b style="{style}"></b>{label}</span>')
    if any(table.get("use") for table in tables):
        legend.append(
            f'<span style="color:{C["p60"]}">보라색 글씨: 이 변경이 그 표를 쓰는 방식</span>'
        )
    return f'<div class="erd-legend">{"".join(legend)}</div><div class="erd-scroll">{"".join(out)}</div>'


def chip(side):
    return f'<span class="chip {"old" if side == "before" else "new"}">{"이전" if side == "before" else "이후"}</span>'


def render_block(block):
    kind = block["type"]
    caption = (
        f'<figcaption>{inline(block["caption"])}</figcaption>'
        if block.get("caption")
        else ""
    )
    if kind == "text":
        return f"<p>{inline(block['text'])}</p>"
    if kind == "callout":
        return f'<div class="callout{" warn" if block.get("kind") == "warn" else ""}">{inline(block["text"])}</div>'
    if kind == "bullets":
        rows = []
        for item in block["items"]:
            if item.get("label"):
                rows.append(
                    f"<li><b>{inline(item['label'])}</b><span>{inline(item['text'])}</span></li>"
                )
            else:
                rows.append(
                    f'<li class="solo"><span>{inline(item["text"])}</span></li>'
                )
        return f'<ul class="kv">{"".join(rows)}</ul>'
    if kind == "table":
        numeric = set(block.get("numeric") or [])
        highlight = set(block.get("highlight") or [])
        head = "".join(
            f'<th{" class=num" if i in numeric else ""}>{inline(h)}</th>'
            for i, h in enumerate(block["headers"])
        )
        body = []
        for r, row in enumerate(block["rows"]):
            cells = "".join(
                f'<td{" class=num" if i in numeric else ""}>{inline(cell)}</td>'
                for i, cell in enumerate(row)
            )
            body.append(f'<tr{" class=pick" if r in highlight else ""}>{cells}</tr>')
        return f'<figure class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>{caption}</figure>'
    if kind == "code":
        return f"<figure>{render_code(block['code'], block.get('lang', 'python'), None, block.get('title', ''))}{caption}</figure>"
    if kind == "compare":
        note = ""
        if block.get("lang") == "sql":
            derived = block.get("sql_source") != "captured"
            note = (
                '<span class="chip est">ORM 코드를 읽고 옮긴 SQL (실행 캡처 아님)</span>'
                if derived
                else '<span class="chip new">실행해 캡처한 SQL</span>'
            )
        sides = []
        for side in ("before", "after"):
            part = block[side]
            title = inline(part["title"]) if part.get("title") else ""
            sides.append(
                f"<div>{render_code(part['code'], block.get('lang'), side, part.get('title', ''))}</div>"
            )
        tail = (
            f'<figcaption>{note} {inline(block.get("caption", ""))}</figcaption>'
            if note or block.get("caption")
            else ""
        )
        return f'<figure class="wide"><div class="pair">{"".join(sides)}</div>{tail}</figure>'
    if kind == "flow":
        return f'<figure class="scroll flowfig">{render_flow(block["steps"])}{caption}</figure>'
    if kind == "sequence":
        diagrams = block["diagrams"]
        if len(diagrams) == 1:
            return f'<figure class="box">{render_sequence(diagrams[0], 720)}{caption}</figure>'
        sides = []
        for side, diagram in zip(("before", "after"), diagrams):
            title = inline(diagram["title"]) if diagram.get("title") else ""
            sides.append(
                f'<div><h4>{chip(side)}{title}</h4><div class="box" style="border:1px solid {C["g15"]};border-radius:12px;padding:10px">{render_sequence(diagram, 540)}</div></div>'
            )
        return f'<figure class="wide"><div class="pair">{"".join(sides)}</div>{caption}</figure>'
    if kind == "tables":
        return f'<figure class="wide erdfig">{render_erd(block["tables"], block.get("relations") or [])}{caption}</figure>'
    if kind == "bars":
        rows = []
        for item in block["items"]:
            top = max(item["before"]["value"], item["after"]["value"]) or 1
            bars = "".join(
                f'<div class="bar {"old" if side == "before" else "new"}" style="width:{max(item[side]["value"] / top * 100, 0.6):.1f}%">'
                f"<em>{esc(item[side]['text'])}</em></div>"
                for side in ("before", "after")
            )
            sub = f"<span>{inline(item['sub'])}</span>" if item.get("sub") else ""
            rows.append(
                f'<div class="row"><div class="name"><b>{inline(item["label"])}</b>{sub}</div><div class="track">{bars}</div></div>'
            )
        note = f'<figcaption>회색 이전, 보라 이후. {inline(block["source"])} {inline(block.get("caption", ""))}</figcaption>'
        return f'<figure class="box"><div class="bars">{"".join(rows)}</div>{note}</figure>'
    raise ValueError(kind)


def render(report, meta):
    pr = meta.get("pr", "")
    repo = meta.get("repo", "")
    pr_url = f"https://github.com/{repo}/pull/{pr}" if repo and pr else ""
    # 머리말 이름: --meta team=<이름>, 없으면 저장소 이름(owner/repo 의 repo), 둘 다 없으면 생략
    team = meta.get("team") or repo.rsplit("/", 1)[-1]
    kpis = ""
    if report.get("kpis"):
        cells = []
        for kpi in report["kpis"]:
            note = f"<small>{inline(kpi['note'])}</small>" if kpi.get("note") else ""
            cells.append(
                f"<div><span>{inline(kpi['label'])}</span><b>{inline(kpi['value'])}</b>{note}</div>"
            )
        kpis = f'<div class="kpis">{"".join(cells)}</div>'
    sections = []
    for section in report["sections"]:
        blocks = "".join(render_block(block) for block in section["blocks"])
        sections.append(f"<h2>{inline(section['heading'])}</h2>{blocks}")
    rows = []
    if pr_url:
        rows.append(
            (
                "PR",
                f'<a href="{esc(pr_url)}">#{esc(pr)}</a> {esc(meta.get("pr_title", ""))}',
            )
        )
    if meta.get("head"):
        rows.append(
            (
                "커밋",
                f"<code>{esc(meta['head'][:9])}</code> ({esc(meta.get('base_ref', ''))} 대상)",
            )
        )
    for row in report.get("sources") or []:
        rows.append((esc(row["label"]), inline(row["text"])))
    rows.append(
        (
            "만든 방법",
            "PR diff 와 코드를 AI 가 읽고 작성. 수치는 PR 본문·테스트에 적힌 값만 사용",
        )
    )
    if meta.get("date"):
        rows.append(("만든 날", esc(meta["date"])))
    foot = "".join(f"<dt>{label}</dt><dd>{value}</dd>" for label, value in rows)
    page = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(report['title'])}</title><style>{CSS}</style></head><body>"
        f'<div class="top"><div class="in">{"<b>" + esc(team) + "</b> · " if team else ""}변경 리포트{" · PR #" + esc(pr) if pr else ""}</div></div>'
        f"<article><h1>{inline(report['title'])}</h1><p class=\"lead\">{inline(report['lead'])}</p>{kpis}{''.join(sections)}</article>"
        f'<div class="foot"><h4>이 리포트의 근거</h4><dl>{foot}</dl></div>{COPY_JS}</body></html>'
    )
    return TOKEN.sub("[REDACTED]", page)


def render_comment(report, meta):
    lines = [
        "<!-- pr-report -->",
        f"### 변경 리포트: {report['title']}",
        "",
        report["lead"],
        "",
    ]
    if report.get("kpis"):
        lines += ["| " + " | ".join(kpi["label"] for kpi in report["kpis"]) + " |"]
        lines += ["|" + "---|" * len(report["kpis"])]
        lines += [
            "| " + " | ".join(str(kpi["value"]) for kpi in report["kpis"]) + " |",
            "",
        ]
    lines += [
        "목차: " + " / ".join(section["heading"] for section in report["sections"]),
        "",
    ]
    return TOKEN.sub("[REDACTED]", "\n".join(lines))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    path, out, comment, meta = argv[1], None, None, {}
    args = argv[2:]
    while args:
        flag = args.pop(0)
        if flag == "--out":
            out = args.pop(0)
        elif flag == "--comment":
            comment = args.pop(0)
        elif flag == "--meta":
            while args and not args[0].startswith("--"):
                key, _, value = args.pop(0).partition("=")
                meta[key] = value
    try:
        with open(path, encoding="utf-8") as handle:
            report = json.load(handle)
    except (OSError, ValueError) as error:
        print(f"report.json 을 읽지 못했습니다: {error}")
        return 1
    problems = check(report)
    if problems:
        print(f"고칠 곳 {len(problems)}건")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("통과")
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(render(report, meta))
    if comment:
        with open(comment, "w", encoding="utf-8") as handle:
            handle.write(render_comment(report, meta))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
