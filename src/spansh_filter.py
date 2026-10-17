"""Spansh 全条件筛选器 - Elite Dangerous 星系 / 空间站
用法见 docs/README_筛选器说明.txt
数据源: https://spansh.co.uk/api (免费, 无需key, 数据与 Inara 同源 EDDN)
"""
import argparse
import json
import sys
import urllib.request
import urllib.error

BASE = "https://spansh.co.uk/api"

# Windows 控制台编码兼容
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ---- 全部可用筛选词条 (根据 spansh.co.uk/stations + /systems 整理) ----
# key = API用的 filters key, value = 说明
STATION_FIELDS = {
    "allegiance": "阵营: Alliance/Empire/Federation/Independent/Pilots Federation...",
    "government": "政体: Corporate/Democracy/Dictatorship/...",
    "state": "系统状态: Boom/Civil War/Famine/...",
    "economy": "兼容写法, 推荐用 primary_economy",
    "primary_economy": "主经济: High Tech/Industrial/Extraction/Refinery/Agriculture/Tourism/...",
    "secondary_economy": "副经济, 同上, 可空",
    "economies": "经济组合 (share%)",
    "type": "空间站类型: Coriolis Starport/Orbis Starport/Ocellus/Dodec/Asteroid base/Outpost/Planetary Outpost/Planetary Port/Settlement/Mega ship/Drake-Class Carrier/...",
    "has_market": "有市场 true/false",
    "has_shipyard": "有船厂 true/false",
    "has_outfitting": "有改装 true/false",
    "has_large_pad": "有大型停机坪 true/false",
    "is_planetary": "是否地面站 true/false (对应 planetary)",
    "planetary": "同上, 旧名",
    "large_pads": "大型垫数量 {min/max}",
    "medium_pads": "中型垫数量 {min/max}",
    "small_pads": "小型垫数量 {min/max}",
    "distance_to_arrival": "到主星距离 LS {min/max}",
    "distance": "到参考点距离 LY {min/max}, 需配合 reference_system/coords",
    "services": "服务多选: Dock/Autodock/Market/Contacts/Refuel/Repair/Restock/Outfitting/Shipyard/Black Market/Interstellar Factors Contact/Material Trader/Technology Broker/Universal Cartographics/Search and Rescue/Missions/Crew Lounge/...",
    "material_trader": "材料商类型: Manufactured/Raw/Encoded",
    "technology_broker": "科技经纪: Human/Guardian/Sirius",
    "ships": "出售船只: Anaconda/Python/Krait MkII/...",
    "modules": "出售模块名/ed_symbol",
    "marketplace": "市场商品名",
    "export_commodities": "出口商品",
    "import_commodities": "进口商品",
    "prohibited_commodities": "违禁品",
    "controlling_faction": "控制派系名 (模糊)",
    "controlling_faction_state": "控制派系状态",
    "controlling_faction_influence": "控制派系影响力 {min/max}",
    "system_name": "所在星系名 (模糊)",
    "system_population": "星系人口 {min/max}",
    "system_power": "星系关联势力: Edmund Mahon/A. Lavigny-Duval/Li Yong-Rui/...",
    "system_power_state": "势力状态: Unoccupied/Exploited/Fortified/Stronghold",
    "system_controlling_power": "控制势力",
    "system_primary_economy": "星系主经济",
    "system_secondary_economy": "星系副经济",
    "system_colonised": "星系是否殖民 true/false",
    "system_being_colonised": "是否殖民中 true/false",
    "body_name": "所在天体名",
    "body_type": "天体类型",
    "body_subtype": "天体子类型",
    "body_has_atmosphere": "天体有大气 true/false",
    "body_has_rings": "天体有环 true/false",
    "body_gravity": "重力 {min/max}",
    "carrier_name": "舰队航母名",
    "carrier_docking_access": "航母停靠权限: all/none/friends/squadron",
    "dssa_carrier": "是否DSSA true/false",
    "name": "空间站名 (模糊)",
    "real_name": "真实名",
    "last_updated_at": "数据更新时间, 如 {min: '2026-01-01'}/{max}",
    "market_last_updated_at": "市场更新时间",
    "shipyard_last_updated_at": "船厂更新时间",
    "outfitting_last_updated_at": "改装更新时间",
}

SYSTEM_FIELDS = {
    "name": "星系名 (模糊/精确)",
    "allegiance": "阵营",
    "government": "政府 (主派系)",
    "state": "状态",
    "economy": "主经济, 推荐用 primary_economy",
    "primary_economy": "主经济",
    "secondary_economy": "副经济",
    "security": "安全等级: High/Medium/Low/Anarchy",
    "population": "人口 {min/max}",
    "needs_permit": "需要许可 true/false",
    "known_permit": "已知许可",
    "is_colonised": "已殖民 true/false (对应 colonised)",
    "colonised": "同上",
    "being_colonised": "殖民中 true/false",
    "body_count": "天体数量 {min/max}",
    "bodies": "天体条件",
    "stations": "空间站条件 (是否有站)",
    "distance": "到参考点 LY {min/max}",
    "distance_to_nearest_populated_system": "到最近有人星系距离",
    "controlling_faction": "控制派系",
    "controlling_faction_state": "控制派系状态",
    "faction_presence": "派系存在",
    "power": "势力多选",
    "controlling_power": "控制势力",
    "power_state": "势力状态",
    "power_state_control_progress": "控制进度 {min/max}",
    "power_state_reinforcement": "加固 {min/max}",
    "power_state_undermining": "破坏 {min/max}",
    "region": "银河区域: Inner Orion Spur/...",
    "landmarks": "地标",
    "landmark_value": "地标价值 {min/max}",
    "estimated_scan_value": "预估扫描价值 {min/max}",
    "estimated_mapping_value": "预估测绘价值 {min/max}",
    "thargoid_war_state": "Thargoid战争状态",
    "thargoid_war_progress": "战争进度",
    "thargoid_war_days_remaining": "剩余天数",
    "thargoid_war_ports_remaining": "剩余港口",
    "synthesis_recipes": "合成配方",
    "last_updated_at": "更新时间",
}

# ---- 字段中文名 (GUI 下拉显示用, 值保持英文原名查库) ----
STATION_FIELDS_CN = {
    "allegiance": "阵营",
    "government": "政体",
    "state": "系统状态",
    "economy": "经济(兼容)",
    "primary_economy": "主经济",
    "secondary_economy": "副经济",
    "economies": "经济构成",
    "type": "空间站类型",
    "has_market": "有市场",
    "has_shipyard": "有船厂",
    "has_outfitting": "有改装厂",
    "has_large_pad": "有大型停机坪",
    "is_planetary": "是否地面站",
    "planetary": "地面站(旧字段)",
    "large_pads": "大型停机坪数",
    "medium_pads": "中型停机坪数",
    "small_pads": "小型停机坪数",
    "distance_to_arrival": "到达距离 ls",
    "distance": "距离(光年)",
    "services": "服务设施",
    "material_trader": "材料商",
    "technology_broker": "科技经纪人",
    "ships": "出售飞船",
    "modules": "出售模块",
    "marketplace": "市场商品",
    "export_commodities": "出口商品",
    "import_commodities": "进口商品",
    "prohibited_commodities": "禁运商品",
    "controlling_faction": "控制派系",
    "controlling_faction_state": "控制派系状态",
    "controlling_faction_influence": "控制派系影响力",
    "system_name": "所在星系名",
    "system_population": "星系人口",
    "system_power": "星系势力",
    "system_power_state": "星系势力状态",
    "system_controlling_power": "星系控制势力",
    "system_primary_economy": "星系主经济",
    "system_secondary_economy": "星系副经济",
    "system_colonised": "星系已殖民",
    "system_being_colonised": "星系殖民中",
    "body_name": "所在天体名",
    "body_type": "天体类型",
    "body_subtype": "天体子类型",
    "body_has_atmosphere": "天体有大气",
    "body_has_rings": "天体有星环",
    "body_gravity": "天体重力",
    "carrier_name": "航母名",
    "carrier_docking_access": "航母停靠权限",
    "dssa_carrier": "DSSA航母",
    "name": "空间站名",
    "real_name": "真实名称",
    "last_updated_at": "数据更新时间",
    "market_last_updated_at": "市场更新时间",
    "shipyard_last_updated_at": "船厂更新时间",
    "outfitting_last_updated_at": "改装更新时间",
}

SYSTEM_FIELDS_CN = {
    "name": "星系名",
    "allegiance": "阵营",
    "government": "政府",
    "state": "状态",
    "economy": "经济(兼容)",
    "primary_economy": "主经济",
    "secondary_economy": "副经济",
    "security": "安全等级",
    "population": "人口",
    "needs_permit": "需要许可",
    "known_permit": "已知许可",
    "is_colonised": "已殖民",
    "colonised": "已殖民(同义)",
    "being_colonised": "殖民中",
    "body_count": "天体数量",
    "bodies": "天体条件",
    "stations": "空间站条件",
    "distance": "距离(光年)",
    "distance_to_nearest_populated_system": "距最近有人星系",
    "controlling_faction": "控制派系",
    "controlling_faction_state": "控制派系状态",
    "faction_presence": "派系存在",
    "power": "势力",
    "controlling_power": "控制势力",
    "power_state": "势力状态",
    "power_state_control_progress": "控制进度",
    "power_state_reinforcement": "加固度",
    "power_state_undermining": "破坏度",
    "region": "银河区域",
    "landmarks": "地标",
    "landmark_value": "地标价值",
    "estimated_scan_value": "预估扫描价值",
    "estimated_mapping_value": "预估测绘价值",
    "thargoid_war_state": "异种战争状态",
    "thargoid_war_progress": "战争进度",
    "thargoid_war_days_remaining": "战争剩余天数",
    "thargoid_war_ports_remaining": "战争剩余港口",
    "synthesis_recipes": "合成配方",
    "last_updated_at": "更新时间",
}


def field_label(kind, en):
    cn = (STATION_FIELDS_CN if kind == "stations" else SYSTEM_FIELDS_CN).get(en, "")
    return f"{cn} ({en})" if cn else en


def parse_field_label(label):
    if label.endswith(")") and "(" in label:
        return label.rsplit("(", 1)[-1][:-1].strip()
    return label.strip()


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "elite-filter/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:2000]}", file=sys.stderr)
        sys.exit(2)


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "elite-filter/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_payload(args):
    if args.filters_file:
        with open(args.filters_file, encoding="utf-8") as f:
            filters = json.load(f)
    else:
        try:
            filters = json.loads(args.filters) if args.filters else {}
        except json.JSONDecodeError as e:
            print(f"filters JSON 解析失败: {e}", file=sys.stderr)
            sys.exit(2)
    try:
        sort = json.loads(args.sort) if args.sort else [{"distance": {"direction": "asc"}}]
    except json.JSONDecodeError as e:
        print(f"sort JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(2)
    payload = {"filters": filters, "sort": sort, "size": args.size, "page": args.page}
    if args.ref_system:
        payload["reference_system"] = args.ref_system
    if args.ref_coords:
        try:
            x, y, z = [float(v) for v in args.ref_coords.split(",")]
            payload["reference_coords"] = {"x": x, "y": y, "z": z}
        except ValueError:
            print("--ref-coords 格式应为 x,y,z, 例如 55.7,17.5,27.1", file=sys.stderr)
            sys.exit(2)
    return payload


def flatten(row, prefix="", out=None):
    out = out if out is not None else {}
    if isinstance(row, dict):
        for k, v in row.items():
            flatten(v, f"{prefix}{k}.", out)
    elif isinstance(row, list):
        out[prefix.rstrip(".")] = f"[{len(row)}项] " + ", ".join(
            str(x.get("name", x) if isinstance(x, dict) else x) for x in row[:5]
        )
    else:
        out[prefix.rstrip(".")] = row
    return out


def main():
    ap = argparse.ArgumentParser(description="Elite Dangerous 全条件筛选器 (Spansh API)")
    ap.add_argument("--kind", choices=["stations", "systems"], default="stations", help="查空间站还是星系")
    ap.add_argument("--filters", default="{}",
                    help="筛选条件JSON, 如 '{\"primary_economy\":{\"value\":[\"High Tech\"]},\"has_market\":{\"value\":true}}'")
    ap.add_argument("--filters-file", default=None, help="从JSON文件读filters, 例 --filters-file ex_station.json, 避免Windows引号转义问题")
    ap.add_argument("--sort", default='[{"distance":{"direction":"asc"}}]', help="排序JSON")
    ap.add_argument("--size", type=int, default=10, help="本页返回条数，建议1~500")
    ap.add_argument("--page", type=int, default=0)
    ap.add_argument("--ref-system", default=None, help="参考星系, 如 Sol, 用于distance排序/过滤")
    ap.add_argument("--ref-coords", default=None, help="参考坐标 x,y,z")
    ap.add_argument("--output", choices=["table", "json"], default="table")
    ap.add_argument("--list-fields", action="store_true", help="列出全部可用筛选词条")
    ap.add_argument("--field-values", default=None, help="查某字段允许值, 如 services / type / power")
    args = ap.parse_args()

    if args.list_fields:
        table = STATION_FIELDS if args.kind == "stations" else SYSTEM_FIELDS
        print(f"=== {args.kind} 全部可用筛选词条 ({len(table)}个) ===")
        for k, v in table.items():
            print(f"{field_label(args.kind, k):40s} {v}")
        print("\nfilters JSON 格式: 枚举 {\"字段\":{\"value\":[...]}}；数值 {\"字段\":{\"comparison\":\"<=>\",\"value\":[x,y]}}；布尔 {\"字段\":{\"value\":true}}")
        print("例: {\"primary_economy\":{\"value\":[\"High Tech\"]},\"distance_to_arrival\":{\"comparison\":\"<=>\",\"value\":[0,1000]}}")
        return

    if args.field_values:
        for kind in ([args.kind] if args.kind else ["stations", "systems"]):
            url = f"{BASE}/{kind}/field_values/{args.field_values}"
            try:
                d = get_json(url)
                vals = d.get("values", [])
                print(f"[{kind}/{args.field_values}] 可选值 ({len(vals)}个):")
                print(", ".join(str(v) for v in vals[:80]))
                return
            except Exception as e:
                print(f"{kind} 查询失败: {e}", file=sys.stderr)
        sys.exit(2)

    payload = build_payload(args)
    url = f"{BASE}/{args.kind}/search"
    print(f"POST {url}\n{json.dumps(payload, ensure_ascii=False)[:800]}", file=sys.stderr)
    res = post_json(url, payload)
    results = res.get("results", [])
    print(f"共匹配约 {res.get('count', '?')} 条, 本页 {len(results)} 条", file=sys.stderr)
    if args.output == "json":
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return
    from result_format import format_ly, format_ls, format_population
    for i, r in enumerate(results):
        if args.kind == "stations":
            print(f"[{i+1}] {r.get('name')} @ {r.get('system_name')} | {r.get('type')} | "
                  f"主经济={r.get('primary_economy')} | 到达={format_ls(r.get('distance_to_arrival'), '?')}ls | "
                  f"距参考={format_ly(r.get('distance'), '?')}ly | 大垫={r.get('has_large_pad')} | "
                  f"市场/船厂/改装={r.get('has_market')}/{r.get('has_shipyard')}/{r.get('has_outfitting')}")
        else:
            print(f"[{i+1}] {r.get('name')} | 人口={format_population(r.get('population'), '?')} | "
                  f"经济={r.get('primary_economy')} | 阵营={r.get('allegiance')} | "
                  f"距参考={format_ly(r.get('distance'), '?')}ly")


if __name__ == "__main__":
    main()
