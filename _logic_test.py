import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
# 内联复刻 main_ui.py 的 _screen_sorted_rows 与 refresh_screen 顺序缓存逻辑
def _prio(r):
    _st = str(r[7] if len(r) > 7 else "")
    if _st in ("正在检票", "检票中"): return 0
    if _st in ("待检票", "正在候车"): return 1
    return 2
def _tmin(r):
    try:
        _t = str(r[4] if len(r) > 4 else "").strip()
        _hh, _mm = _t.split(":")
        return int(_hh) * 60 + int(_mm)
    except Exception:
        return 24 * 60 + 9999
def sort_rows(rows):
    return sorted(rows, key=lambda r: (_prio(r), _tmin(r)))
# 模拟 refresh_screen 的顺序缓存（与 main_ui.py 修改后一致）
_screen_order = None
def simulate(rows):
    global _screen_order
    new_keys = [str(r[0]) for r in rows]
    prev = _screen_order
    changed = prev != new_keys
    _screen_order = list(new_keys)
    return changed
# 测试数据
rows = []
for i in range(10):
    rows.append([f"G{i+1:04d}", "高铁", "丽水", "杭州东", f"{8+i}:00", f"A{i%3+1}", str(i%6+1), "待检票" if i%3 else "停止检票", f"{10+i}:00"])
rows[0][7] = "正在检票"
out = sort_rows(rows)
assert out[0][7] == "正在检票"
c1 = simulate(out)
c2 = simulate(out)
assert c1 is True and c2 is False
rows2 = [list(r) for r in rows]; rows2[3][7] = "正在检票"
out2 = sort_rows(rows2)
c3 = simulate(out2)
assert c3 is True
same = [["G100","高铁","a","b","09:00","A1","1","待检票","11:00"],
        ["G101","高铁","a","b","09:00","A2","2","待检票","11:00"]]
out3 = sort_rows(same)
assert [r[0] for r in out3] == ["G100","G101"]
print("大屏修复逻辑验证全部通过:")
print(f"  1. 正在检票最前 -> OK ({out[0][0]})")
print(f"  2. 首次重排=True / 数据未变不重排=False -> OK")
print(f"  3. 状态变化触发重排=True -> OK")
print(f"  4. 稳定排序保持相对顺序 -> OK")
print(f"  5. 10车次状态序列: {[r[7] for r in out]}")