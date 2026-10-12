"""字段候选值: 船名/模块名本地全量内置 + Spansh field_values 增量补充, 给GUI第三格做下拉/联想."""
import difflib
import json
import os
import threading
import urllib.parse
import urllib.request
from runtime_paths import data_file

BASE = "https://spansh.co.uk/api"
CACHE_FILE = data_file("field_values_cache.json")
SPECS_FILE = data_file("module_specs_cache.json")
_mem = {}
_lock = threading.Lock()
_refreshing = set()
_refreshed = set()
_specs = None  # {小写模块名: {"name": 原文, "class": [int], "rating": [str]}}
_specs_dirty = False

# 模块等级/级别封闭集合 (游戏机制决定, 本地内置)
BUNDLED_MODULE_CLASSES = [0, 1, 2, 3, 4, 5, 6, 7, 8]
BUNDLED_MODULE_RATINGS = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
# 各模块默认规格子集 (全量普查实际在售数据内置; 磁盘学习库与运行时学习只增不减)
# 格式: {"模块原文名": {"class": [int], "rating": [str]}}
BUNDLED_MODULE_SPECS = {
    "AX Missile Rack": {"class": [2, 3], "rating": ["A", "B"]},
    "AX Multi-Cannon": {"class": [2, 3], "rating": ["C", "E", "F"]},
    "Abrasion Blaster": {"class": [1], "rating": ["D"]},
    "Advanced Docking Computer": {"class": [1], "rating": ["E"]},
    "Advanced Missile Rack": {"class": [1, 2], "rating": ["B"]},
    "Advanced Multi-Cannon": {"class": [1, 2], "rating": ["E", "F"]},
    "Advanced Planetary Approach Suite": {"class": [1], "rating": ["I"]},
    "Advanced Plasma Accelerator": {"class": [3], "rating": ["B"]},
    "Auto Field-Maintenance Unit": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["A", "B", "C", "D", "E"]},
    "Balanced Power Distributor": {"class": [5], "rating": ["A"]},
    "Beam Laser": {"class": [1, 2, 3, 4], "rating": ["A", "C", "D", "E", "F"]},
    "Bi-Weave Shield Generator": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["C"]},
    "Burst Laser": {"class": [1, 2, 3, 4], "rating": ["D", "E", "F", "G"]},
    "Business Class Passenger Cabin": {"class": [3, 4, 5, 6], "rating": ["D"]},
    "Cannon": {"class": [1, 2, 3, 4], "rating": ["B", "C", "D", "E", "F"]},
    "Cargo Rack": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["E"]},
    "Cargo Scanner": {"class": [0], "rating": ["A", "B", "C", "D", "E"]},
    "Caustic Sink Launcher": {"class": [0], "rating": ["I"]},
    "Chaff Launcher": {"class": [0], "rating": ["I"]},
    "Collector Limpet Controller": {"class": [1, 3, 5, 7], "rating": ["A", "B", "C", "D", "E"]},
    "Concord Cannon": {"class": [2], "rating": ["D"]},
    "Corrosion Resistant Cargo Rack": {"class": [1, 4], "rating": ["E", "F"]},
    "Cytoscrambler Burst Laser": {"class": [1], "rating": ["F"]},
    "Decontamination Limpet Controller": {"class": [1, 3, 5, 7], "rating": ["E"]},
    "Detailed Surface Scanner": {"class": [1], "rating": ["C", "I"]},
    "Double Screaming Fragment Cannon": {"class": [1, 3], "rating": ["C", "E"]},
    "Economy Class Passenger Cabin": {"class": [2, 3, 4, 5, 6], "rating": ["E"]},
    "Electronic Countermeasure": {"class": [0], "rating": ["F"]},
    "Enduring Feedback Rail Gun": {"class": [2], "rating": ["B"]},
    "Enforcer Cannon": {"class": [1], "rating": ["F"]},
    "Enhanced AX Missile Rack": {"class": [2, 3], "rating": ["B", "D", "E"]},
    "Enhanced AX Multi-Cannon": {"class": [2, 3], "rating": ["B", "C", "D", "E"]},
    "Enhanced Performance Thrusters": {"class": [2, 3], "rating": ["A"]},
    "Enhanced Xeno Scanner": {"class": [0], "rating": ["C"]},
    "Enzyme Missile Rack": {"class": [2], "rating": ["B"]},
    "Experimental Weapon Stabiliser": {"class": [3, 5], "rating": ["F"]},
    "Exposing Missiles": {"class": [3], "rating": ["A"]},
    "Extended Cargo Rack": {"class": [5, 6], "rating": ["E"]},
    "Far-Reaching Abrasion Blaster": {"class": [1], "rating": ["D"]},
    "Fighter Hangar": {"class": [5, 6, 7], "rating": ["D"]},
    "First Class Passenger Cabin": {"class": [4, 5, 6], "rating": ["C"]},
    "Force Impact Cannon": {"class": [4], "rating": ["B"]},
    "Fragment Cannon": {"class": [1, 2, 3], "rating": ["A", "C", "D", "E"]},
    "Frame Shift Drive": {"class": [2, 3, 4, 5, 6, 7, 8], "rating": ["A", "B", "C", "D", "E"]},
    "Frame Shift Drive (SCO)": {"class": [2, 3, 4, 5, 6, 7, 8], "rating": ["A", "B", "C", "D", "E"]},
    "Frame Shift Drive Interdictor": {"class": [1, 2, 3, 4], "rating": ["A", "B", "C", "D", "E"]},
    "Frame Shift Wake Scanner": {"class": [0], "rating": ["A", "B", "C", "D", "E"]},
    "Fuel Scoop": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["A", "B", "C", "D", "E"]},
    "Fuel Tank": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["C"]},
    "Fuel Transfer Limpet Controller": {"class": [1, 3, 5, 7], "rating": ["A", "B", "C", "D", "E"]},
    "Guardian FSD Booster": {"class": [1, 2, 3, 4, 5], "rating": ["H"]},
    "Guardian Gauss Cannon": {"class": [1, 2], "rating": ["B", "D"]},
    "Guardian Hull Reinforcement": {"class": [1, 2, 3, 4, 5], "rating": ["D", "E"]},
    "Guardian Hybrid Power Distributor": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["A"]},
    "Guardian Hybrid Power Plant": {"class": [2, 3, 4, 5, 6, 7, 8], "rating": ["A"]},
    "Guardian Module Reinforcement": {"class": [1, 2, 3, 4, 5], "rating": ["D", "E"]},
    "Guardian Nanite Torpedo Pylon": {"class": [2, 3], "rating": ["I"]},
    "Guardian Plasma Charger": {"class": [1, 2, 3], "rating": ["B", "C", "D", "E", "F"]},
    "Guardian Shard Cannon": {"class": [1, 2, 3], "rating": ["A", "C", "D", "F"]},
    "Guardian Shield Reinforcement": {"class": [1, 2, 3, 4, 5], "rating": ["D", "E"]},
    "Hatch Breaker Limpet Controller": {"class": [1, 3, 5, 7], "rating": ["A", "B", "C", "D", "E"]},
    "Heat Sink Launcher": {"class": [0], "rating": ["I"]},
    "Heavy Duty Module Reinforcement Package": {"class": [5], "rating": ["D"]},
    "High-Yield Enzyme Missile Rack": {"class": [2], "rating": ["B"]},
    "Hull Reinforcement Package": {"class": [1, 2, 3, 4, 5], "rating": ["D", "E"]},
    "Imperial Hammer Rail Gun": {"class": [2], "rating": ["B"]},
    "Kill Warrant Scanner": {"class": [0], "rating": ["A", "B", "C", "D", "E"]},
    "Large Planetary Vehicle Hangar": {"class": [2, 4, 6], "rating": ["F"]},
    "Life Support": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["A", "B", "C", "D", "E"]},
    "Lightweight Alloy": {"class": [1], "rating": ["C", "I"]},
    "Lockdown Seeker Missile Rack": {"class": [2], "rating": ["B"]},
    "Long Range Detailed Surface Scanner": {"class": [1], "rating": ["I"]},
    "Long Range Mining Laser": {"class": [1], "rating": ["D"]},
    "Luxury Class Passenger Cabin": {"class": [5, 6], "rating": ["B"]},
    "Meta Alloy Hull Reinforcement": {"class": [1, 2, 3, 4, 5], "rating": ["D", "E"]},
    "Military Grade Composite": {"class": [1], "rating": ["A", "I"]},
    "Mine Launcher": {"class": [1, 2], "rating": ["I"]},
    "Mining Lance": {"class": [1], "rating": ["D"]},
    "Mining Laser": {"class": [1, 2], "rating": ["D"]},
    "Mining Multi Limpet Controller": {"class": [3], "rating": ["C", "E"]},
    "Mining Volley Repeater": {"class": [3], "rating": ["C"]},
    "Mirrored Surface Composite": {"class": [1], "rating": ["A", "I"]},
    "Missile Rack": {"class": [1, 2, 3], "rating": ["A", "B"]},
    "Mk II Ablative Lightweight Alloys": {"class": [1], "rating": ["C"]},
    "Mk II Ablative Military Grade Composite": {"class": [1], "rating": ["A"]},
    "Mk II Ablative Mirrored Surface Composite": {"class": [1], "rating": ["A"]},
    "Mk II Ablative Reactive Surface Composite": {"class": [1], "rating": ["A"]},
    "Mk II Ablative Reinforced Alloys": {"class": [1], "rating": ["B"]},
    "Mk II Agile Boost Thrusters": {"class": [5], "rating": ["A"]},
    "Mk II Business Class Passenger Cabin": {"class": [3, 4, 5, 6], "rating": ["D"]},
    "Mk II Cargo Rack": {"class": [7, 8], "rating": ["D"]},
    "Mk II Economy Class Passenger Cabin": {"class": [2, 3, 4, 5, 6], "rating": ["E"]},
    "Mk II Gravity Optimised Thrusters": {"class": [7], "rating": ["A"]},
    "Mk II Large Planetary Vehicle Hangar": {"class": [2, 4, 6], "rating": ["F"]},
    "Mk II Mining Multi-Limpet Controller": {"class": [5], "rating": ["A"]},
    "Mk II Plasma Shock Accelerator": {"class": [3], "rating": ["B"]},
    "Mk II Supercharge Optimised Frame Shift Drive (SCO)": {"class": [8], "rating": ["A"]},
    "Mk II Vessel Hangar": {"class": [5, 6, 7], "rating": ["D"]},
    "MkII Business Class Passenger Cabin": {"class": [3, 4, 5], "rating": ["C"]},
    "MkII Economy Class Passenger Cabin": {"class": [2, 3, 4, 5], "rating": ["D"]},
    "Module Reinforcement Package": {"class": [1, 2, 3, 4, 5], "rating": ["D", "E"]},
    "Multi-Cannon": {"class": [1, 2, 3, 4], "rating": ["A", "C", "E", "F", "G"]},
    "Operations Multi Limpet Controller": {"class": [3], "rating": ["B", "C"]},
    "Overloaded Beam Laser": {"class": [4], "rating": ["A"]},
    "Pacifier Frag-Cannon": {"class": [3], "rating": ["C"]},
    "Pack-Hound Missile Rack": {"class": [2], "rating": ["B"]},
    "Planetary Approach Suite": {"class": [1], "rating": ["I"]},
    "Planetary Vehicle Hangar": {"class": [2, 4, 6], "rating": ["G", "H"]},
    "Plasma Accelerator": {"class": [2, 3, 4], "rating": ["A", "B", "C"]},
    "Point Defence": {"class": [0], "rating": ["I"]},
    "Power Distributor": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["A", "B", "C", "D", "E"]},
    "Power Plant": {"class": [2, 3, 4, 5, 6, 7, 8], "rating": ["A", "B", "C", "D", "E"]},
    "Prismatic Shield Generator": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["A"]},
    "Prospector Limpet Controller": {"class": [1, 3, 5, 7], "rating": ["A", "B", "C", "D", "E"]},
    "Pulse Disruptor Laser": {"class": [2], "rating": ["E"]},
    "Pulse Laser": {"class": [1, 2, 3, 4], "rating": ["A", "D", "E", "F", "G"]},
    "Pulse Wave Analyser": {"class": [0], "rating": ["A", "B", "C", "D", "E"]},
    "Pulse Wave Xeno Scanner": {"class": [0], "rating": ["C"]},
    "Rail Gun": {"class": [1], "rating": ["D"]},
    "Rapid Phase Multi-Cannon": {"class": [2], "rating": ["E"]},
    "Reactive Surface Composite": {"class": [1], "rating": ["A", "I"]},
    "Recon Limpet Controller": {"class": [1, 3, 5, 7], "rating": ["E"]},
    "Refinery": {"class": [1, 2, 3, 4], "rating": ["A", "B", "C", "D", "E"]},
    "Regenerative Burst Laser": {"class": [2], "rating": ["F"]},
    "Reinforced Alloy": {"class": [1], "rating": ["B", "I"]},
    "Remote Release Flak Launcher": {"class": [2], "rating": ["B"]},
    "Remote Release Flechette Launcher": {"class": [2], "rating": ["B"]},
    "Repair Limpet Controller": {"class": [1, 3, 5, 7], "rating": ["A", "B", "C", "D", "E"]},
    "Rescue Multi Limpet Controller": {"class": [3], "rating": ["C", "D"]},
    "Research Limpet Controller": {"class": [1], "rating": ["E"]},
    "Retributor Beam Laser": {"class": [1], "rating": ["E"]},
    "Rocket Propelled FSD Disruptor": {"class": [2], "rating": ["B"]},
    "Seeker Missile Rack": {"class": [1, 2, 3], "rating": ["A", "B"]},
    "Seismic Charge Launcher": {"class": [2], "rating": ["B"]},
    "Sensors": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["A", "B", "C", "D", "E"]},
    "Shield Booster": {"class": [0], "rating": ["A", "B", "C", "D", "E"]},
    "Shield Cell Bank": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["A", "B", "C", "D", "E"]},
    "Shield Generator": {"class": [1, 2, 3, 4, 5, 6, 7, 8], "rating": ["A", "B", "C", "D", "E"]},
    "Shock Cannon": {"class": [1, 2, 3], "rating": ["C", "D", "E", "F"]},
    "Shock Mine Launcher": {"class": [1], "rating": ["I"]},
    "Shutdown Field Neutraliser": {"class": [0], "rating": ["F"]},
    "Standard Docking Computer": {"class": [1], "rating": ["E"]},
    "Sub-Surface Displacement Missile": {"class": [1, 2], "rating": ["B"]},
    "Sub-Surface Extraction Missile": {"class": [2], "rating": ["B"]},
    "Supercruise Assist": {"class": [1], "rating": ["E"]},
    "Support Focused Power Distributor": {"class": [3, 4, 6], "rating": ["A", "D"]},
    "Thargoid Pulse Neutraliser": {"class": [0], "rating": ["E"]},
    "Thrusters": {"class": [2, 3, 4, 5, 6, 7, 8], "rating": ["A", "B", "C", "D", "E"]},
    "Torpedo Pylon": {"class": [1, 2, 3], "rating": ["I"]},
    "Universal Multi Limpet Controller": {"class": [7], "rating": ["A", "C"]},
    "Vessel Hangar": {"class": [5, 6, 7], "rating": ["D"]},
    "Xeno Multi Limpet Controller": {"class": [3], "rating": ["B", "C"]},
    "Xeno Scanner": {"class": [0], "rating": ["E"]},
}

# 本地全量内置 (2026-10-04 从官方 field_values 拉取; 船48个/模块153个, 无大小写重名)
# 本地永远是权威来源: 后台刷新只增不减, 离线照样可用。
BUNDLED_OPTIONS = {
    "stations/ships": ["Sidewinder", "Hauler", "Cobra MkIII", "Type-6 Transporter", "Adder", "Eagle", "Krait MkII", "Panther Clipper MkII", "Cobra MkV", "Viper MkIII", "Krait Phantom", "Asp Explorer", "Type-8 Transporter", "Type-7 Transporter", "Mandalay", "Dolphin", "Type-9 Heavy", "Viper MkIV", "Diamondback Explorer", "Python", "Vulture", "Keelback", "Anaconda", "Caspian Explorer", "Type-11 Prospector", "Asp Scout", "Diamondback Scout", "Python MkII", "Beluga Liner", "Lynx Highliner", "Mamba", "Orca", "Corsair", "Fer-de-Lance", "Kestrel Mk II", "Cobra MkIV", "Type-10 Defender", "Alliance Chieftain", "Alliance Challenger", "Imperial Courier", "Imperial Eagle", "Alliance Crusader", "Imperial Clipper", "Federal Corvette", "Imperial Cutter", "Federal Dropship", "Federal Assault Ship", "Federal Gunship"],
    "stations/modules": ["Fuel Scoop", "Power Distributor", "Sensors", "Life Support", "Shield Cell Bank", "Auto Field-Maintenance Unit", "Power Plant", "Shield Generator", "Thrusters", "Frame Shift Drive", "Frame Shift Drive (SCO)", "Lightweight Alloy", "Reinforced Alloy", "Refinery", "Military Grade Composite", "Prospector Limpet Controller", "Frame Shift Drive Interdictor", "Hatch Breaker Limpet Controller", "Fuel Transfer Limpet Controller", "Collector Limpet Controller", "Reactive Surface Composite", "Mirrored Surface Composite", "Repair Limpet Controller", "Hull Reinforcement Package", "Beam Laser", "Pulse Laser", "Cannon", "Module Reinforcement Package", "Multi-Cannon", "Planetary Vehicle Hangar", "Cargo Rack", "Fuel Tank", "Burst Laser", "Bi-Weave Shield Generator", "Fragment Cannon", "Shield Booster", "Sub-Surface Displacement Missile", "Recon Limpet Controller", "Cargo Scanner", "Kill Warrant Scanner", "Economy Class Passenger Cabin", "Frame Shift Wake Scanner", "Pulse Wave Analyser", "Missile Rack", "Mining Laser", "Torpedo Pylon", "Support Focused Power Distributor", "Business Class Passenger Cabin", "Seeker Missile Rack", "Prismatic Shield Generator", "Vessel Hangar", "MkII Economy Class Passenger Cabin", "Mine Launcher", "Xeno Multi Limpet Controller", "Mk II Cargo Rack", "Plasma Accelerator", "Seismic Charge Launcher", "Rail Gun", "Mining Multi Limpet Controller", "First Class Passenger Cabin", "Operations Multi Limpet Controller", "Rescue Multi Limpet Controller", "Large Planetary Vehicle Hangar", "Mk II Large Planetary Vehicle Hangar", "MkII Business Class Passenger Cabin", "Mk II Vessel Hangar", "Extended Cargo Rack", "Decontamination Limpet Controller", "Chaff Launcher", "Heat Sink Launcher", "Standard Docking Computer", "Supercruise Assist", "Research Limpet Controller", "Abrasion Blaster", "Electronic Countermeasure", "Advanced Docking Computer", "Shock Mine Launcher", "Fighter Hangar", "Double Screaming Fragment Cannon", "Advanced Planetary Approach Suite", "AX Multi-Cannon", "Mk II Mining Multi-Limpet Controller", "AX Missile Rack", "Meta Alloy Hull Reinforcement", "Planetary Approach Suite", "Long Range Detailed Surface Scanner", "Luxury Class Passenger Cabin", "Far-Reaching Abrasion Blaster", "Lockdown Seeker Missile Rack", "Long Range Mining Laser", "Mk II Plasma Shock Accelerator", "Enduring Feedback Rail Gun", "Point Defence", "Mining Volley Repeater", "Rapid Phase Multi-Cannon", "Heavy Duty Module Reinforcement Package", "Detailed Surface Scanner", "Exposing Missiles", "Force Impact Cannon", "Enhanced AX Multi-Cannon", "Regenerative Burst Laser", "Mk II Agile Boost Thrusters", "Mk II Supercharge Optimised Frame Shift Drive (SCO)", "Overloaded Beam Laser", "Mk II Gravity Optimised Thrusters", "Remote Release Flak Launcher", "Balanced Power Distributor", "Universal Multi Limpet Controller", "Mk II Economy Class Passenger Cabin", "Mk II Ablative Lightweight Alloys", "Mk II Ablative Reinforced Alloys", "Mk II Ablative Military Grade Composite", "Mk II Ablative Reactive Surface Composite", "Mk II Ablative Mirrored Surface Composite", "Xeno Scanner", "Mk II Business Class Passenger Cabin", "Pack-Hound Missile Rack", "Imperial Hammer Rail Gun", "Shutdown Field Neutraliser", "Enforcer Cannon", "Advanced Plasma Accelerator", "Retributor Beam Laser", "Pulse Disruptor Laser", "Concord Cannon", "Rocket Propelled FSD Disruptor", "Mining Lance", "Pacifier Frag-Cannon", "Cytoscrambler Burst Laser", "Thargoid Pulse Neutraliser", "Enhanced Xeno Scanner", "Shock Cannon", "Advanced Multi-Cannon", "Advanced Missile Rack", "Enhanced AX Missile Rack", "High-Yield Enzyme Missile Rack", "Corrosion Resistant Cargo Rack", "Enzyme Missile Rack", "Remote Release Flechette Launcher", "Guardian Shield Reinforcement", "Experimental Weapon Stabiliser", "Guardian Hull Reinforcement", "Guardian Module Reinforcement", "Guardian Hybrid Power Distributor", "Guardian Hybrid Power Plant", "Guardian Shard Cannon", "Guardian Plasma Charger", "Caustic Sink Launcher", "Guardian FSD Booster", "Pulse Wave Xeno Scanner", "Guardian Nanite Torpedo Pylon", "Sub-Surface Extraction Missile", "Guardian Gauss Cannon", "Enhanced Performance Thrusters"],
}


def _load_disk():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_disk(d):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


def _http_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "elite-filter/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _norm_values(d):
    v = (d or {}).get("values")
    if isinstance(v, list):
        return [str(x) for x in v]
    if isinstance(v, dict):
        for k in ("name", "value", "values"):
            if isinstance(v.get(k), list):
                return [str(x) for x in v[k]]
        # 兜底: 第一个是list的key
        for vv in v.values():
            if isinstance(vv, list) and vv and isinstance(vv[0], (str, int, float)):
                return [str(x) for x in vv]
    return []


def _merge_lists(*lists):
    """按大小写去重合并, 保持首现顺序 (本地项永远排前面, 永不丢失)。"""
    seen, out = set(), []
    for lst in lists:
        for x in lst or []:
            k = str(x).casefold()
            if k not in seen:
                seen.add(k)
                out.append(str(x))
    return out


def _merge_ints(*lists):
    """整数去重合并, 保持首现顺序 (本地项永远排前面, 永不丢失)。"""
    seen, out = set(), []
    for lst in lists:
        for x in lst or []:
            try:
                v = int(x)
            except (TypeError, ValueError):
                continue
            if v not in seen:
                seen.add(v)
                out.append(v)
    return out


# 模块等级/级别封闭集合 (游戏机制决定, 本地内置; 后台只增不减)
BUNDLED_MODULE_CLASSES = [0, 1, 2, 3, 4, 5, 6, 7, 8]
BUNDLED_MODULE_RATINGS = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]


def _bg_refresh(kind, field):
    """后台增量补充: 成功才合并(只增不减), 失败静默; 每会话每字段只刷一次。"""
    key = f"{kind}/{field}"
    with _lock:
        if key in _refreshing or key in _refreshed:
            return
        _refreshing.add(key)

    def work():
        try:
            opts = _norm_values(_http_json(f"{BASE}/{kind}/field_values/{field}"))
            if opts:
                with _lock:
                    merged = _merge_lists(BUNDLED_OPTIONS.get(key, []),
                                          _mem.get(key, []), opts)
                    _mem[key] = merged
                    disk = _load_disk()
                    disk[key] = merged
                _save_disk(disk)
                with _lock:
                    _refreshed.add(key)
        except Exception:
            pass
        finally:
            with _lock:
                _refreshing.discard(key)

    threading.Thread(target=work, daemon=True).start()


def get_options(kind, field):
    """船/模块走本地全量名单(秒回, 离线可用), 后台增量补充;
    其他枚举字段走缓存+网络, 布尔/数值/自由文本返回 []。"""
    key = f"{kind}/{field}"
    with _lock:
        hit = key in _mem
        opts = list(_mem[key]) if hit else None
    if hit:
        if key in BUNDLED_OPTIONS:
            _bg_refresh(kind, field)
        return opts
    if key in BUNDLED_OPTIONS:
        disk = _load_disk()
        cached = disk.get(key) if isinstance(disk.get(key), list) else []
        merged = _merge_lists(BUNDLED_OPTIONS[key], cached)
        with _lock:
            _mem[key] = merged
        if merged != cached:
            disk[key] = merged
            _save_disk(disk)
        _bg_refresh(kind, field)
        return list(merged)
    disk = _load_disk()
    if key in disk and isinstance(disk[key], list):
        with _lock:
            _mem[key] = disk[key]
        return list(disk[key])
    try:
        d = _http_json(f"{BASE}/{kind}/field_values/{field}")
        opts = _norm_values(d)
    except Exception:
        opts = []
    with _lock:
        _mem[key] = opts
    if opts:
        disk[key] = opts
        _save_disk(disk)
    return list(opts)


def similar_in(options, query, limit=5):
    """本地名单相似度排序, 返回 [(候选, 相似度0~1)]。"""
    q = (query or "").strip().casefold()
    if not q:
        return []
    scored = [(o, difflib.SequenceMatcher(None, q, str(o).casefold()).ratio())
              for o in options]
    scored.sort(key=lambda t: -t[1])
    return [(o, s) for o, s in scored[:limit] if s > 0]


def similar_modules(name, limit=5):
    """模块名纠错候选 (本地153个全量, 无网络)。"""
    return similar_in(get_options("stations", "modules"), name, limit)


def similar_ships(name, limit=5):
    """船名纠错候选 (本地48个全量, 无网络)。"""
    return similar_in(get_options("stations", "ships"), name, limit)


def _clean_spec_entry(name, val):
    """规格条目清洗 -> (小写键, entry) 或 None。"""
    if not isinstance(val, dict):
        return None
    name = str(val.get("name") or name).strip()
    if not name:
        return None
    classes = sorted({_safe_int(x) for x in (val.get("class") or [])} - {None})
    ratings = sorted({str(x).upper() for x in (val.get("rating") or [])
                      if str(x).strip()})
    order = {v: i for i, v in enumerate(BUNDLED_MODULE_RATINGS)}
    ratings.sort(key=lambda v: (order.get(v, 999), v))
    return name.casefold(), {"name": name, "class": classes, "rating": ratings}


def _merge_spec_entry(entry, val):
    """磁盘/新增规格并入已有条目 (只增不减)。返回新增个数。"""
    cleaned = _clean_spec_entry(val.get("name") or entry["name"], val)
    if cleaned is None:
        return 0
    added = 0
    for cls in cleaned[1]["class"]:
        if cls not in entry["class"]:
            entry["class"].append(cls)
            added += 1
    entry["class"].sort()
    order = {v: i for i, v in enumerate(BUNDLED_MODULE_RATINGS)}
    for rat in cleaned[1]["rating"]:
        if rat not in entry["rating"]:
            entry["rating"].append(rat)
            added += 1
    entry["rating"].sort(key=lambda v: (order.get(v, 999), v))
    return added


def _load_specs():
    """规格学习库: 内置普查打底 + 磁盘学习库只增不减, 并清洗。"""
    global _specs
    with _lock:
        if _specs is not None:
            return _specs
        raw = {}
        try:
            with open(SPECS_FILE, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                raw = loaded
        except Exception:
            raw = {}
        cleaned = {}
        for name, spec in BUNDLED_MODULE_SPECS.items():
            item = _clean_spec_entry(name, {"name": name, **spec})
            if item is not None:
                cleaned[item[0]] = item[1]
        for key, val in raw.items():
            name = str(val.get("name") or key).strip() if isinstance(val, dict) else str(key)
            ck = name.casefold()
            if ck in cleaned and isinstance(val, dict):
                _merge_spec_entry(cleaned[ck], val)
            else:
                item = _clean_spec_entry(key, val)
                if item is not None:
                    cleaned[item[0]] = item[1]
        _specs = cleaned
        return _specs


def _safe_int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def save_module_specs():
    """学习库有新增才写盘。返回 True 表示写过盘。"""
    global _specs_dirty
    with _lock:
        if not _specs_dirty or _specs is None:
            return False
        data = {v["name"]: {"name": v["name"], "class": v["class"],
                            "rating": v["rating"]} for v in _specs.values()}
        _specs_dirty = False
    try:
        with open(SPECS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def learn_module_specs(items):
    """从在售条目 [{name, class, rating}] 学习各模块见过的规格。返回新增个数。"""
    global _specs_dirty
    specs = _load_specs()
    added = 0
    with _lock:
        for it in items or []:
            if not isinstance(it, dict) or not str(it.get("name") or "").strip():
                continue
            name = str(it["name"]).strip()
            key = name.casefold()
            entry = specs.get(key)
            if entry is None:
                entry = {"name": name, "class": [], "rating": []}
                specs[key] = entry
            cls = _safe_int(it.get("class"))
            if cls is not None and cls not in entry["class"]:
                entry["class"].append(cls)
                entry["class"].sort()
                added += 1
            rat = str(it.get("rating") or "").strip().upper()
            if rat and rat not in entry["rating"]:
                entry["rating"].append(rat)
                order = {v: i for i, v in enumerate(BUNDLED_MODULE_RATINGS)}
                entry["rating"].sort(key=lambda v: (order.get(v, 999), v))
                added += 1
        if added:
            _specs_dirty = True
    return added


def get_module_specs(name):
    """某模块学过的规格 (classes, ratings)；没学过返回 (None, None) 用全集。"""
    specs = _load_specs()
    with _lock:
        entry = specs.get((name or "").strip().casefold())
        if entry is None:
            return None, None
        return list(entry["class"]), list(entry["rating"])


def _spec_options(known, bundled):
    """已知子集按封闭集合的 canonical 顺序排，未知余项追加在后。"""
    if not known:
        return list(bundled)
    order = {str(v).upper(): i for i, v in enumerate(bundled)}
    in_set = sorted(known, key=lambda v: (order.get(str(v).upper(), 999), str(v)))
    return in_set


def get_module_classes(name=None):
    """等级下拉候选：指定模块且学过 → 已见子集，否则全集 0~8。返回 str 列表。"""
    if name:
        known, _ = get_module_specs(name)
        if known:
            return [str(v) for v in _spec_options(known, BUNDLED_MODULE_CLASSES)]
    return [str(v) for v in BUNDLED_MODULE_CLASSES]


def get_module_ratings(name=None):
    """级别下拉候选：指定模块且学过 → 已见子集，否则全集。返回 str 列表。"""
    if name:
        _, known = get_module_specs(name)
        if known:
            return [str(v) for v in _spec_options(known, BUNDLED_MODULE_RATINGS)]
    return list(BUNDLED_MODULE_RATINGS)


def suggest_systems(query, limit=10):
    """星系名联想, 用于距离参考点 / system_name 辅助输入."""
    q = (query or "").strip()
    if len(q) < 2:
        return []
    try:
        u = f"{BASE}/systems/field_values/system_names?q={urllib.parse.quote(q)}"
        d = _http_json(u, timeout=15)
        out = []
        # 返回可能是 list[dict] 或 dict
        items = d if isinstance(d, list) else d.get("min_max") or d.get("values") or []
        if isinstance(items, dict):
            items = items.get("name", []) if isinstance(items.get("name"), list) else []
        for it in items[:limit]:
            if isinstance(it, dict):
                out.append(it.get("name", ""))
            else:
                out.append(str(it))
        return [x for x in out if x]
    except Exception:
        return []


def prefetch_common(kind, fields):
    def work():
        for f in fields:
            try:
                get_options(kind, f)
            except Exception:
                pass
    threading.Thread(target=work, daemon=True).start()


def similar_systems(name, limit=8):
    """星系名纠错候选: 用全名/前5字/前3字分别拉联想, 按相似度排序。
    返回 [(候选名, 相似度0~1)]。"""
    q = (name or "").strip()
    if len(q) < 2:
        return []
    seen = {}
    for prefix in dict.fromkeys([q, q[:5], q[:3]]):
        if len(prefix) < 2:
            continue
        for cand in suggest_systems(prefix, limit=20):
            if cand.lower() not in seen:
                seen[cand.lower()] = cand
    scored = [(cand, difflib.SequenceMatcher(None, q.lower(), cand.lower()).ratio())
              for cand in seen.values()]
    scored.sort(key=lambda t: -t[1])
    return scored[:limit]
