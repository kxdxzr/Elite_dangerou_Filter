"""Powerplay 空间站模板：关联势力、未占领、环带检索和逐势力距离回退。"""
import math

import filter_engine as eng


POWERS = (
    "A. Lavigny-Duval", "Aisling Duval", "Archon Delaine", "Denton Patreus",
    "Edmund Mahon", "Felicia Winters", "Jerome Archer", "Li Yong-Rui",
    "Nakato Kaine", "Pranav Antal", "Yuri Grom", "Zemina Torval",
)
POWER_LABELS = {p: p for p in POWERS}
POWER_LABELS["A. Lavigny-Duval"] = "Arissa Lavigny-Duval"
STATE_NOTE = "Spansh Unoccupied；未区分 Expansion / Contested，合并关系尚未样本验证。"
MAX_RESULTS_PER_POWER = 5


def normalize_power(value):
    raw = str(value or "").strip().casefold()
    for power in POWERS:
        if raw in (power.casefold(), POWER_LABELS[power].casefold()):
            return power
    raise ValueError("请选择有效的 Power 势力")


def _finite(value, label):
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label}必须是有限数字") from None
    if isinstance(value, bool) or not math.isfinite(result):
        raise ValueError(f"{label}必须是有限数字")
    return result


def template_conditions(reference, powers, min_ly, max_ly, arrival):
    return [
        dict(type="distance", ref_system=reference, min_ly=min_ly, max_ly=max_ly, mode="inside"),
        dict(type="field", field="has_large_pad", op="true"),
        dict(type="field", field="distance_to_arrival", op="between", min=0, max=arrival),
        dict(type="field", field="planetary", op="false"),
        dict(type="field", field="type", op="not in", values=["Drake-Class Carrier"]),
        dict(type="field", field="system_power", op="in", values=list(powers)),
        dict(type="field", field="system_power_state", op="in", values=["Unoccupied"]),
    ]


def _is_colonisation_ship(row):
    # Spansh 可能将殖民船标为 Planetary Outpost 且 is_planetary=false；不能只检查类型。
    markers = ("colonisation ship", "colonization ship", "colonisationship", "colonizationship")
    return any(marker in str(row.get(key) or "").casefold()
               for key in ("name", "real_name", "type") for marker in markers)


def _eligible(row, arrival):
    """模板必需信息逐行复核，未知不当作满足；航母按类型统一排除。"""
    value = eng._num(row.get("distance_to_arrival"))
    station_type = row.get("type")
    return (row.get("has_large_pad") in (True, 1, "true")
            and not _is_colonisation_ship(row)
            and row.get("is_planetary") in (False, 0, "false")
            and isinstance(station_type, str) and bool(station_type.strip())
            and "carrier" not in station_type.casefold()
            and value is not None and math.isfinite(value) and 0 <= value <= arrival
            and str(row.get("system_power_state", "")).casefold() == "unoccupied")


def search_powerplay(reference="Ngurii", power="A. Lavigny-Duval", all_powers=False,
                     min_ly=200, max_ly=220, max_pages=20, progress=None, stop=None):
    """返回 (info, groups)。每组仅标准结果或回退结果；未取完不推断无命中。

    全势力使用势力并集查询，按行关联势力分组；空组在标准分页完成后批量回退。
    每轮每页500条，max_pages分别约束标准和回退轮。每组先按ly、再按Ls排序，最多返回5站。
    """
    reference = str(reference or "").strip()
    if not reference:
        raise ValueError("请填写参考星系")
    lo, hi = _finite(min_ly, "最小距离"), _finite(max_ly, "最大距离")
    if not 0 <= lo <= hi or hi <= 0:
        raise ValueError("距离须满足 0 ≤ 最小距离 ≤ 最大距离，且最大距离大于0")
    if isinstance(max_pages, bool) or not isinstance(max_pages, int) or max_pages < 1:
        raise ValueError("每轮最多页数必须是正整数")
    selected = list(POWERS) if all_powers else [normalize_power(power)]
    groups = {p: dict(power=p, rows=[], arrival_limit=100, complete=False, status="未完成",
                      station_count=0, system_count=0, shown_count=0)
              for p in selected}
    info = dict(reference=reference, min_ly=lo, max_ly=hi, scanned=0,
                complete=False, notes=[], corrections=[], state_note=STATE_NOTE, unverifiable=0)

    def cancelled():
        return stop is not None and stop.is_set()

    def collect(powers, arrival):
        notes, corrections = [], []
        prefix = f"≤{arrival} Ls，{len(powers)} 个势力"

        def report(message, detail=None):
            eng._report(progress, f"{prefix}：{message}", **(detail or {}))

        rows, _, scanned = eng.search(
            "stations", template_conditions(info["reference"], powers, lo, hi, arrival),
            want=max_pages * 500 + 1, max_pages=max_pages, page_size=500,
            progress=report, stop=stop, notes=notes, corrections=corrections)
        info["scanned"] += scanned
        info["notes"].append(f"{prefix}：" + "；".join(notes))
        info["corrections"].extend(corrections)
        info["reference"] = dict(corrections).get(info["reference"], info["reference"])
        unverifiable = 0
        for row in rows:
            if _is_colonisation_ship(row):
                # 明确不合格，而非数据未知；不能阻止空组触发1000 Ls回退。
                continue
            names = {n.casefold() for n in eng._names(row.get("system_power"))}
            matched = [p for p in powers if p.casefold() in names]
            if not _eligible(row, arrival) or not matched:
                unverifiable += 1
                continue
            for p in matched:
                item = dict(row)
                item["_powerplay_distance"] = next(iter(row.get("_distances", {}).values()), None)
                raw_distance = eng._num(row.get("distance"))
                item["_powerplay_sort_distance"] = (raw_distance
                    if raw_distance is not None and math.isfinite(raw_distance)
                    else item["_powerplay_distance"])
                item["_powerplay_limit"] = arrival
                groups[p]["rows"].append(item)
        info["unverifiable"] += unverifiable
        # 缺少关键字段不能据此确认无结果，也不能触发距离回退。
        complete = ("候选分页已取完" in notes and not unverifiable
                    and not any("缺少本地复核字段" in n for n in notes))
        for p in powers:
            group = groups[p]
            group.update(arrival_limit=arrival, complete=complete)
            group["status"] = ("标准范围" if arrival == 100 else "放宽范围") if group["rows"] else "无结果"
            if not complete:
                group["status"] += "（未完成）" if group["rows"] else ""  # 空组始终标为未完成
                if not group["rows"]:
                    group["status"] = "未完成"
        return complete

    if cancelled():
        info["notes"].append("已手动停止，尚未发送请求")
        return info, groups
    primary_complete = collect(selected, 100)
    empty = [p for p in selected if not groups[p]["rows"]]
    if primary_complete and empty and not cancelled():
        collect(empty, 1000)
    elif primary_complete and empty and cancelled():
        for p in empty:
            groups[p].update(complete=False, status="未完成")
    for group in groups.values():
        group["rows"].sort(key=lambda r: (r.get("_powerplay_sort_distance")
                                          if r.get("_powerplay_sort_distance") is not None else float("inf"),
                                          eng._num(r.get("distance_to_arrival")) or 0,
                                          r.get("system_name", ""), r.get("name", "")))
        group["station_count"] = len(group["rows"])
        group["system_count"] = len({r.get("system_id64") or r.get("system_name")
                                     for r in group["rows"]})
        group["rows"] = group["rows"][:MAX_RESULTS_PER_POWER]
        group["shown_count"] = len(group["rows"])
    info["complete"] = all(g["complete"] for g in groups.values())
    return info, groups
