"""Exact provenance checks plus deliberately conservative factual gates."""

import re
import unicodedata


def locate(ref, sources):
    source = sources.get(ref["source_id"])
    if source is None:
        return None, "unknown_source", "引用的资料编号不存在。"
    # Exact, contiguous match. No fuzzy matching, whitespace removal, or ellipsis expansion.
    offset = source["text"].find(ref["quote"])
    if offset < 0:
        return None, "quote_not_found", "引文不是对应资料正文中的连续原文。"
    return {
        "source_id": source["id"], "source_title": source["title"],
        "source_url": source["url"], "quote": ref["quote"],
        "start": offset, "end": offset + len(ref["quote"]),
    }, None, None


_DIGITS = dict(zip("零〇一二两三四五六七八九", [0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9]))
_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000}


def _chinese_number(token):
    if not any(c in _UNITS for c in token):
        return str(int("".join(str(_DIGITS[c]) for c in token)))
    total = section = current = 0
    for c in token:
        if c in _DIGITS:
            current = _DIGITS[c]
        else:
            unit = _UNITS[c]
            if unit >= 10000:
                if unit == 100000000:
                    total = (total + section + current) * unit
                else:
                    total += (section + current) * unit
                section = 0
            else:
                section += (current or 1) * unit
            current = 0
    return str(total + section + current)


def numbers(text):
    text = unicodedata.normalize("NFKC", text)
    found = set()
    for token in re.findall(r"\d+(?:\.\d+)?", text):
        found.add(token.lstrip("0") or "0")
    for token in re.findall(r"[零〇一二两三四五六七八九十百千万亿]+(?=余?\s*[年道个项种元块岁世纪小时天月日批])", text):
        found.add(_chinese_number(token))
    return found


TICKET_TOPIC = re.compile(r"门票|票价|入场费|入园费|ticket", re.I)
MONEY_ASSERTION = re.compile(
    r"免费|免票|免门票|不收.{0,4}(?:费|钱)|无需.{0,4}(?:费|钱)|不花钱|优惠|折扣|零元|[￥¥]|"
    r"(?:\d+(?:\.\d+)?|[零〇一二两三四五六七八九十百千万]+)\s*(?:元|块钱|人民币)")

# These are factual assertions, even if surrounded by promotional language.
# The gates require explicit wording; they never establish semantic support by themselves.
PRODUCTION_EXCLUSION = re.compile(
    r"(?:不是|并非|绝非|不靠|不用|不使用|不采用|不经过|没有采用|无需)[^。！？!?；;\n]{0,24}"
    r"(?:印刷厂|工厂|流水线|机器|机械|工业|量产|批量)")
MANUAL_TERM = re.compile(r"手工|手绘|手刻|手印|手制|手作|人工|手上功夫|靠手")
ALL_MANUAL = re.compile(
    r"纯手工|全手工|(?:全程|全部|所有工序|各道工序|整个过程|整个流程|每(?:一)?(?:步|道|个环节)|道道工序)"
    r"[^。！？!?；;\n]{0,16}(?:手工|靠手|手上功夫|人工|手作)")
HERITAGE_TERM = re.compile(r"非遗|非物质文化遗产")


def is_ticket_gap_notice(text):
    """Recognize only standard missing-price notices, not arbitrary ticket paragraphs."""
    clean = re.sub(r"[^\w\u4e00-\u9fff]", "", text)
    return re.fullmatch(
        r"(?:门票价格|门票信息|门票|票价|入场费|入园费)"
        r"(?:资料不足|待核验|待确认|未提供|未知|暂无资料|尚不明确)+", clean
    ) is not None


def has_ticket_price(text):
    # Require a ticket-related subject AND an asserted price in the same sentence.
    return any(TICKET_TOPIC.search(s) and MONEY_ASSERTION.search(s)
               for s in re.split(r"[。！？!?；;\n]", text))


def guard_segment(text, quotes):
    combined = "\n".join(quotes)
    reasons = []
    missing = numbers(text) - numbers(combined)
    if missing:
        reasons.append(("unsupported_number", "文案中的数字、数量或年份未在所引原文中找到：" + "、".join(sorted(missing))))
    if MONEY_ASSERTION.search(text) and not has_ticket_price(combined):
        reasons.append(("unsupported_price", "所引资料未提供可支持该费用、免费或优惠说法的门票依据。"))
    if PRODUCTION_EXCLUSION.search(text) and not PRODUCTION_EXCLUSION.search(combined):
        reasons.append(("unsupported_production_method", "排除工厂、流水线或机器生产属于事实断言；所引原文未明确支持该生产方式判断。"))
    if ALL_MANUAL.search(text) and not ALL_MANUAL.search(combined):
        reasons.append(("unsupported_all_manual", "“每一步都靠手”等全程手工判断需要覆盖全部工序的明确依据；民间版画或单道工序不能证明。"))
    elif MANUAL_TERM.search(text) and not MANUAL_TERM.search(combined):
        reasons.append(("unsupported_manual_method", "所引资料未明确提供该手工制作方式，不能从“民间”或工序名称自行推断。"))
    if HERITAGE_TERM.search(text) and not HERITAGE_TERM.search(combined):
        reasons.append(("unsupported_heritage_designation", "所引资料正文未提供非遗认定依据；“非遗清单”等称呼也需要依据，不能由来源标题、链接或宣传任务补足。"))
    if re.search(r"待核验|待确认|资料不足|尚不明确", text):
        reasons.append(("explicit_uncertainty", "生成文案自身包含未确认信息。"))
    return reasons


def mandatory_questions(request):
    if TICKET_TOPIC.search(request["brief"]) and not any(
        has_ticket_price(s["text"]) for s in request["sources"]
    ):
        return [{"code": "missing_ticket_price", "topic": "门票价格",
                 "reason": "提供的资料未给出门票价格、免费或优惠信息，资料不足，待核验。"}]
    return []
