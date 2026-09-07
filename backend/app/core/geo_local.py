"""
本地行政区域检索模块。

优先从 admin_divisions.json 检索地名坐标/adcode/层级，减少第三方地图 API 调用。
检索失败时由调用方调第三方，结果可通过 save_entry() 增量回写本地。

数据更新策略：
- 全量更新：scripts/update_admin_divisions.py 从高德 district_query 拉取
- 增量更新：geocode 第三方命中后自动 save_entry()
- 手动触发：后台 POST /api/admin/geo/refresh

功能特性：
- 懒加载行政区域数据（线程安全）
- 按名称检索行政区域，支持别名/简称
- 查找所有同名（含别名）的行政区域，用于同名消歧
- 按adcode检索行政区域
- 获取某个地点的所有上级行政区域
- 增量保存行政区域数据
- 强制重新加载数据

使用方式：
    from app.core.geo_local import lookup, lookup_all, save_entry

    # 按名称检索行政区域
    entry = lookup("杭州")
    # 返回 {name, adcode, level, lng, lat, parent}

    # 查找所有同名的行政区域
    entries = lookup_all("朝阳区")
    # 用于同名消歧（北京朝阳区/长春朝阳区）
"""
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

_DATA_PATH = Path(__file__).resolve().parent / "data" / "admin_divisions.json"
_cache = None
_lock = threading.Lock()


def _load() -> dict:
    """懒加载行政区域数据（线程安全）"""
    global _cache
    if _cache is not None:
        return _cache
    with _lock:
        if _cache is not None:
            return _cache
        if _DATA_PATH.exists():
            _cache = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
        else:
            _cache = {"by_name": {}, "by_adcode": {}, "stats": {}}
        return _cache


def _reload():
    """强制重新加载（save_entry 后调用）"""
    global _cache
    with _lock:
        _cache = None


def _entries_at(by_name: dict, key: str) -> list:
    """获取 by_name[key] 对应的所有条目（兼容 dict 和 list 两种存储格式）。

    同名地点（如北京朝阳区/长春朝阳区）存储为 list，单个地点存储为 dict。
    """
    val = by_name.get(key)
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def lookup(name: str) -> Optional[dict]:
    """按名称检索行政区域，支持别名/简称。同名地点返回第一个。

    返回 {name, adcode, level, lng, lat, parent}，未命中返回 None。
    level: province / city / district
    """
    if not name:
        return None
    d = _load()
    by_name = d.get("by_name", {})
    base = name.strip()
    # 候选名称：原名 + 加后缀 + 去后缀
    candidates = [base]
    for suffix in ["市", "省", "区", "县"]:
        if not base.endswith(suffix):
            candidates.append(base + suffix)
        else:
            candidates.append(base.rstrip(suffix))
    # 去重保序
    seen = set()
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            entries = _entries_at(by_name, c)
            if entries:
                return entries[0]
    return None


def lookup_all(name: str) -> list:
    """查找所有同名（含别名）的行政区域，返回列表。用于同名消歧。"""
    if not name:
        return []
    d = _load()
    by_name = d.get("by_name", {})
    base = name.strip()
    candidates = [base]
    for suffix in ["市", "省", "区", "县"]:
        if not base.endswith(suffix):
            candidates.append(base + suffix)
        else:
            candidates.append(base.rstrip(suffix))
    # 收集所有匹配，去重（按 name+parent+level）
    results = []
    seen_keys = set()
    for c in candidates:
        if c:
            for entry in _entries_at(by_name, c):
                key = f"{entry.get('name','')}|{entry.get('parent','')}|{entry.get('level','')}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    results.append(entry)
    return results


def is_ambiguous(name: str) -> bool:
    """检测地名是否存在同名歧义（不同 parent 的同名地点）。"""
    results = lookup_all(name)
    if len(results) <= 1:
        return False
    parents = {e.get("parent") or "root" for e in results}
    return len(parents) > 1


def lookup_with_context(name: str, context_province: str = None,
                        context_city: str = None) -> tuple:
    """上下文优先的同名消歧检索。

    返回 (entry, candidates, resolved)：
    - resolved=True：已通过上下文消歧，entry 为最佳匹配
    - resolved=False：无法消歧，candidates 为所有候选（由上层对话确认）

    消歧优先级：
    1. 同名地点中 parent 包含 context_province 的优先
    2. 同名地点中 name/parent 包含 context_city 的优先
    3. 只有一个候选时直接返回
    """
    candidates = lookup_all(name)
    if not candidates:
        return None, [], False
    if len(candidates) == 1:
        return candidates[0], candidates, True

    # 按上下文评分
    def score(entry):
        s = 0
        parent = (entry.get("parent") or "").lower()
        entry_name = (entry.get("name") or "").lower()
        if context_province:
            cp = context_province.lower()
            if cp in parent or cp in entry_name:
                s += 10
            # 模糊匹配：去后缀
            for suffix in ["省", "市", "自治区"]:
                if cp.rstrip(suffix) in parent:
                    s += 8
                    break
        if context_city:
            cc = context_city.lower()
            if cc in parent or cc in entry_name:
                s += 5
        return s

    scored = [(score(e), e) for e in candidates]
    scored.sort(key=lambda x: -x[0])
    best_score, best_entry = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else -1

    # 如果有上下文但最佳候选分数为0（不匹配上下文），返回 None（让第三方 API 处理）
    if (context_province or context_city) and best_score == 0:
        return None, candidates, False

    # 如果最佳候选分数明显高于第二名（>3分），认为已消歧
    if best_score > 0 and best_score - second_score > 3:
        return best_entry, candidates, True

    # 无法消歧，返回所有候选
    return None, candidates, False


def lookup_by_adcode(adcode: str) -> Optional[dict]:
    """按 adcode 检索行政区域"""
    if not adcode:
        return None
    d = _load()
    return d.get("by_adcode", {}).get(adcode)


def get_children(parent_name: str) -> list:
    """获取某行政区域的子级列表（如省→市、市→区县）"""
    d = _load()
    results = []
    for val in d.get("by_name", {}).values():
        entries = val if isinstance(val, list) else [val]
        for e in entries:
            if e.get("parent") == parent_name:
                results.append(e)
    return results


def save_entry(entry: dict) -> bool:
    """增量写入一条行政区域数据（geocode 第三方命中后调用）。

    entry 需含 name/lng/lat，可选 adcode/level/parent。
    同名不同 parent 的地点存储为 list。写入后自动持久化到 admin_divisions.json。
    返回是否写入成功。
    """
    name = (entry.get("name") or "").strip()
    if not name or "lng" not in entry or "lat" not in entry:
        return False
    d = _load()
    by_name = d.setdefault("by_name", {})
    by_adcode = d.setdefault("by_adcode", {})

    new_entry = {
        "name": name,
        "adcode": entry.get("adcode", ""),
        "level": entry.get("level", ""),
        "lng": float(entry["lng"]),
        "lat": float(entry["lat"]),
        "parent": entry.get("parent"),
    }

    existing_entries = _entries_at(by_name, name)
    # 检查是否已有相同 name+parent 的条目
    merged = False
    for i, e in enumerate(existing_entries):
        if e.get("parent") == new_entry["parent"]:
            # 合并：保留 adcode 等字段，新条目覆盖坐标
            existing_entries[i] = {
                "name": name,
                "adcode": new_entry["adcode"] or e.get("adcode", ""),
                "level": new_entry["level"] or e.get("level", ""),
                "lng": new_entry["lng"],
                "lat": new_entry["lat"],
                "parent": new_entry["parent"] or e.get("parent"),
            }
            merged = True
            new_entry = existing_entries[i]
            break

    if not merged:
        existing_entries.append(new_entry)

    # 存储：单条目用 dict，多条目用 list
    if len(existing_entries) == 1:
        by_name[name] = existing_entries[0]
    else:
        by_name[name] = existing_entries

    # 别名：去后缀（别名只指向第一个条目，消歧时通过 lookup_all 展开）
    for suffix in ["市", "省", "区", "县"]:
        if name.endswith(suffix):
            alias = name[:-len(suffix)]
            if alias and alias != name and alias not in by_name:
                by_name[alias] = existing_entries[0]
            break

    if new_entry.get("adcode"):
        by_adcode[new_entry["adcode"]] = new_entry

    # 更新统计
    stats = d.setdefault("stats", {})
    lvl = new_entry.get("level", "")
    if lvl:
        stats[lvl] = stats.get(lvl, 0) + 1

    # 持久化
    try:
        _DATA_PATH.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        _reload()
        return True
    except Exception:
        return False


def stats() -> dict:
    """返回数据统计信息"""
    d = _load()
    by_name = d.get("by_name", {})
    all_entries = []
    for val in by_name.values():
        if isinstance(val, list):
            all_entries.extend(val)
        else:
            all_entries.append(val)
    return {
        "version": d.get("version", ""),
        "updated_at": d.get("updated_at", ""),
        "total": len(by_name),
        "total_entries": len(all_entries),
        "with_adcode": sum(1 for e in all_entries if e.get("adcode")),
        "ambiguous_names": sum(1 for val in by_name.values() if isinstance(val, list)),
        "stats": d.get("stats", {}),
    }
