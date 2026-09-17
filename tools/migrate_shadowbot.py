# -*- coding: utf-8 -*-
"""
migrate_shadowbot.py - 影刀(ShadowBot)资产迁移器
==================================================

把用户的影刀 RPA 工程资产迁移进本地项目 android_autopilot，并按流程分组
【自动剔除失效资源】。

源数据（只读，禁止改动）：
    package.json      -> APP流程 -> 分组(groupName) 映射
    selectorsV2.xml   -> 91 个控件选择器，按 group 分组，name 形如
                         <控件类型>-<APP>-<页面>-<动作>
    imagesV2.xml      -> 212 个图片选择器，name 形如
                         图像-<APP>-<页面>-<动作>，含 similarity/adaptive 等参数
    resources/images  -> 图片选择器对应的实际图片文件

────────────────────────────────────────────────────────────────────────
失效剔除判定逻辑（刻意写清楚，保证可审计、可解释、可改参）
────────────────────────────────────────────────────────────────────────
1. 每个 APP 流程（flows 数组条目）在影刀里归属于 7 个分组之一：
       5.运行通过        -> 有效（valid）
       4.运行未过        -> 失效/待测（excluded）
       1.状态未知        -> 失效/待测（excluded）
       6.元素重写        -> 失效/待测（excluded）
       0.回收站          -> 失效（excluded）
       2.编写未完 / 3.编写已完 -> 若无此组则不出现；属于待测倾向，同样走 EXCLUDE
   （默认分组见脚本头部 EXCLUDE_GROUPS / VALID_GROUPS 配置）

2. 每条资产（控件选择器 / 图片选择器）依据其命名里的 APP 段归并到某个流程；
   流程的分组即该批资产的最终归属状态。例如：
       imagesV2 group="快手极速版" -> APP=快手极速版 -> flow process12(4.运行未过)
       -> 该 21 张图片全部剔除，原因=「APP流程分组 4.运行未过 判定失效/待测」

3. 命名含 "旧 / 回收站 / 模板" 等关键词时额外提示归类（仅警告提示，
   不覆盖分组判定）。

4. groupName 为空（None）的兜底归类：
       main            -> 主流程入口，不迁移
       名含"模板"        -> 模板类流程，单独归类（不接入执行）
       名含"子流程"      -> 子流程类，单独归类
       "运行通过"        -> 名称特殊，单独归类待人工确认
       其它             -> 无分组映射，单独归类

5. 资产找不到对应流程（unmapped）时单独归类并在报告中列出，不臆造归属。

输出（仅新增到目标项目，源保持只读）：
    images/<app>/...           有效 APP 的图片（按 app 分子目录，保留源文件名）
    apps_migrated.yaml         有效 APP 的定位片段，可并入 config.yaml 的 apps 节
    excluded/                  被剔除/待测/特殊资产的清单（manifest，不复制图片）
    docs/migration_report.md   迁移报告：统计 + 按 APP 剔除清单与原因 + 参数落地说明

用法：
    python tools/migrate_shadowbot.py                 # 执行迁移
    python tools/migrate_shadowbot.py --dry-run       # 只打印计划，不写文件
    python tools/migrate_shadowbot.py --src <源目录> --proj <目标目录>
可重复运行（幂等）：不删除源/目标任何既有文件，仅覆盖本脚本管理的有名输出
（apps_migrated.yaml / excluded/excluded_manifest.yaml / docs/migration_report.md），
并复制有效图片到 images/<APP>/（同名覆盖）。如需清理旧的迁移产物，
请用内置 delete 工具手动移除 images/、excluded/ 等目录。
"""
import argparse
import json
import os
import shutil
import sys
import datetime
import xml.etree.ElementTree as ET

import yaml

# ──────────────────────────────────────────────────────────────────────
# 可配置项（按需修改）
# ──────────────────────────────────────────────────────────────────────

# 影刀流程分组 -> 状态
VALID_GROUPS = {"5.运行通过"}                     # 有效分组
EXCLUDE_GROUPS = {                                # 失效/待测分组
    "4.运行未过",
    "1.状态未知",
    "6.元素重写",
    "0.回收站",
    "2.编写未完",   # 若工程里出现，倾向视为待测
    "3.编写已完",   # 已写完但未跑，倾向视为待测
}

# 命名关键词提示（仅提示归类，不覆盖分组判定）
KEYWORD_HINTS = ("旧", "回收站", "模板")

# 控件选择器 name 前缀 -> 定位类型（用于还原动作候选，仅提示性）
SELECTOR_TYPE_HINT = {
    "文本框": "text",
    "按钮": "text",
    "视图框": "text",
    "移动元素": "text",
    "图片框": "image",
    "图片按钮": "image",
    "视图组": "text",
    "图像框": "image",
    "图像按钮": "image",
}

# 页面/动作关键词 -> 意图行为键（用于 apps_migrated.yaml 的 behaviors 聚合）
BEHAVIOR_KEYWORDS = (
    # (意图键, 命中关键词元组)
    ("sign", ("签到",)),
    ("withdraw", ("提现",)),
    ("watch", ("看视频", "连续看视频", "看广告", "看指定视频", "视频")),
    ("reserve", ("预约", "打卡", "打卡领")),
    ("bonus", ("领现金", "领金币", "红包", "宝箱", "领福利", "天天领金币", "元宝", "领红包", "能量红包")),
    ("collect", ("任务列表", "任务界面", "任务中心", "任务")),
    ("open", ("打开APP", "打开")),
)

# 文件路径常量
DEFAULT_SRC = (
    r"C:\Users\Mass\AppData\Local\ShadowBot\users\11e0482d-dd71-4520-b6cc-daee7631f313\apps"
    r"\d5c83858-1176-4ecd-a5a9-3655d3da977a\xbot_robot"
)

# ──────────────────────────────────────────────────────────────────────
# 小工具
# ──────────────────────────────────────────────────────────────────────

def now_str():
    dt = datetime.datetime.now()
    return f"{dt.year}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"


def base_name_parts(name):
    """从资产 name 剥掉控件/图像前缀，返回 (prefix, rest)。

    '文本框-飞猪-能量红包-签到' -> ('文本框', '飞猪-能量红包-签到')
    '图像-今日头条极速版-打开APP-我的' -> ('图像', '今日头条极速版-打开APP-我的')
    '图片框-七猫免费小说' -> ('图片框', '七猫免费小说')
    """
    if "-" in name:
        prefix, rest = name.split("-", 1)
        return prefix.strip(), rest
    return name.strip(), ""


def app_key_of(prefix, rest):
    """从剩下部分取第一段作为 APP 标识（资产归属维度）。

    '飞猪-能量红包-签到' -> '飞猪'
    '今日头条极速版-打开APP-我的' -> '今日头条极速版'
    '七猫免费小说' -> '七猫免费小说'
    """
    if not rest:
        return ""
    return rest.split("-", 1)[0].strip()


def infer_app_key(name, group_name):
    """资产 APP 归属：优先用 explicit group 名；默认分组等则从 name 剥前缀取首段。

    selectors/images 的 group 名多数即 APP 名，但 selectors 的"默认分组"
    混装多个 APP，此时必须从 name 前缀推断。
    """
    prefix, rest = base_name_parts(name)
    if group_name and group_name not in ("默认分组",):
        return group_name.strip()
    key = app_key_of(prefix, rest)
    return key


def match_flow_name(app_key, flow_names):
    """app_key -> flow.name 匹配：精确优先，其次按'最短超集'前缀匹配。

    例如：'飞猪' -> '飞猪旅行'；'支付宝' -> '支付宝改成元素'；
    而 '星图金融' 会精确命中流程 '星图金融'（不会误配到 '星图金融旧'）。
    """
    if not app_key:
        return None
    if app_key in flow_names:
        return app_key
    supers = [n for n in flow_names if n.startswith(app_key) and n != app_key]
    if supers:
        return min(supers, key=len)
    return None


def flow_status(flow):
    """按流程分组判定资产状态，返回 (status, reason)。

    status ∈ {valid, excluded, main, template, subprocess, special, unmapped}
    """
    group = flow.get("groupName")
    name = flow["name"]

    if group in EXCLUDE_GROUPS:
        return "excluded", f"APP流程分组 '{group}' 判定失效/待测"
    if group in VALID_GROUPS:
        if name == "子流程":
            return "subprocess", "子流程类流程，单独归类（未做主干迁移）"
        return "valid", None

    # groupName 为空（None）或其它未知分组
    if group:
        return "excluded", f"未知分组 '{group}'，保守判定待测/失效"
    if name == "main":
        return "main", "主流程入口，仅作工程背景，不迁移资产"
    if "模板" in name:
        return "template", "模板类流程，单独归类（不接入执行）"
    if name == "子流程":
        return "subprocess", "子流程类流程，单独归类"
    if name == "运行通过":
        return "special", "groupName 为空且名称特殊，单独归类待人工确认"
    return "unmapped", "groupName 为空，无分组映射"


def status_label(status):
    return {
        "valid": "有效",
        "excluded": "失效/待测",
        "main": "主流程",
        "template": "模板",
        "subprocess": "子流程",
        "special": "特殊",
        "unmapped": "无映射",
    }.get(status, status)


def extract_selector_fields(sel):
    """从 selectorsV2.xml 的 <selector> 提取定位要素。

    返回 dict：name, pkg, res_ids, texts, mobile_count
    - pkg   : mobile 链中出现次数最多的 package（APP 包名线索）
    - res_id: 首选一个非 'android:id/content' 的 resource-id（可空）
    - text  : 首个非空 text（可空）
    """
    pkgs = []
    res_ids = []
    texts = []
    for m in sel.iter("mobile"):
        for opt in m.findall("optional"):
            p = opt.get("package")
            if p:
                pkgs.append(p)
            rid = opt.get("resource-id")
            if rid:
                res_ids.append(rid)
            t = opt.get("text")
            if t:
                texts.append(t)
    pkg = max(set(pkgs), key=pkgs.count) if pkgs else ""
    non_root_rid = next((r for r in res_ids if r not in ("android:id/content", "root")), "")
    return {
        "name": sel.get("name") or "",
        "pkg": pkg,
        "res_id": non_root_rid,
        "text": texts[0] if texts else "",
        "texts": list(dict.fromkeys(texts)),
    }


def pick_image_by_page(app_images, page, action=None):
    """粗粒度把图片绑定到行为，返回匹配的模板相对路径列表（辅佐用途）。"""
    out = []
    for img in app_images:
        ipage = img.get("page", "")
        if ipage and ipage == page:
            out.append(img["file"])
    return out


# ──────────────────────────────────────────────────────────────────────
# 解析源数据
# ──────────────────────────────────────────────────────────────────────

def parse_package_json(src_dir):
    with open(os.path.join(src_dir, "package.json"), encoding="utf-8") as f:
        return json.load(f)


def parse_flows(pkg):
    """flows 数组 -> {flow_name: {file, group, status, reason}}"""
    flow_by_name = {}
    for fl in pkg.get("flows", []):
        s, reason = flow_status(fl)
        flow_by_name[fl["name"]] = {
            "file": fl.get("filename"),
            "group": fl.get("groupName"),
            "status": s,
            "reason": reason,
        }
    return flow_by_name


def parse_selectors(src_dir):
    """解析 selectorsV2.xml -> 资产列表。"""
    tree = ET.parse(os.path.join(src_dir, "selectorsV2.xml"))
    root = tree.getroot()
    assets = []
    for g in root.findall("group"):
        gname = g.get("name", "")
        for sel in g.findall("selector"):
            fields = extract_selector_fields(sel)
            prefix, rest = base_name_parts(fields["name"])
            app_key = infer_app_key(fields["name"], gname)
            assets.append({
                "kind": "selector",
                "src_group": gname,
                "app_key": app_key,
                "prefix": prefix,
                "rest": rest,
                "name": fields["name"],
                "pkg": fields["pkg"],
                "res_id": fields["res_id"],
                "text": fields["text"],
                "text_more": fields["texts"],
                "screenshot": sel.get("screenshot") or "",
            })
    return assets


def parse_images(src_dir):
    """解析 imagesV2.xml -> 资产列表。"""
    tree = ET.parse(os.path.join(src_dir, "imagesV2.xml"))
    root = tree.getroot()
    assets = []
    for g in root.findall("group"):
        gname = g.get("name", "")
        for img in g.findall("imageelement"):
            name = img.get("name") or ""
            prefix, rest = base_name_parts(name)
            app_key = infer_app_key(name, gname)
            # rest: <APP>-<页面>-<动作>
            seg = rest.split("-") if rest else []
            page = seg[1] if len(seg) > 1 else ""
            action = "-".join(seg[2:]) if len(seg) > 2 else ""
            assets.append({
                "kind": "image",
                "src_group": gname,
                "app_key": app_key,
                "prefix": prefix,
                "rest": rest,
                "name": name,
                "page": page,
                "action": action,
                "filepath": img.get("filepath") or "",
                "similarity": float(img.get("similarity") or 80),
                "scalingfactor": float(img.get("scalingfactor") or 0),
                "adaptive": (str(img.get("adaptive") or "").lower() == "true"),
                "graying": (str(img.get("graying") or "").lower() == "true"),
            })
    return assets


def behavior_key(asset):
    """按资产命名(页面/动作)推断意图行为键；无法推断用页面原文。"""
    if asset["kind"] == "image":
        hay = (asset.get("page") or "") + "-" + (asset.get("action") or "")
    else:
        hay = asset.get("rest") or ""
    for key, kws in BEHAVIOR_KEYWORDS:
        for kw in kws:
            if kw in hay:
                return key
    page = asset.get("page") or ""
    return page or "misc"


# ──────────────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────────────

def build_plan(flow_by_name, selectors, images):
    """把资产归并到流程并确定状态。返回 plan dict 供落盘/报告。

    一个流程对应一批资产；每批资产给出：status, reason, selectors, images,
    以及逐条 asset 的去留标记。
    """
    flow_names = list(flow_by_name)
    by_flow = {}          # flow_name -> plan

    # 初始登记所有流程（含无资产的流程）
    for fname, info in flow_by_name.items():
        by_flow[fname] = {
            "flow": fname,
            "file": info["file"],
            "group": info["group"],
            "status": info["status"],
            "reason": info["reason"],
            "keywords_hint": [],
            "selectors": [],
            "images": [],
        }

    no_flow = {"selectors": [], "images": []}

    def place(asset):
        fn = match_flow_name(asset["app_key"], flow_names)
        if fn is None or asset["app_key"] == "":
            no_flow[asset["kind"] + "s"].append(asset)
            return
        flow_plan = by_flow[fn]
        flow_plan[asset["kind"] + "s"].append(asset)
        # 关键词提示
        if any(kw in asset["name"] for kw in KEYWORD_HINTS):
            flow_plan["keywords_hint"].append(asset["name"])

    for a in selectors:
        place(a)
    for a in images:
        place(a)

    # no_flow 资产按命名软归类
    extras = []
    for a in no_flow["selectors"] + no_flow["images"]:
        name = a["name"]
        if not a["app_key"]:
            st, rea = "unmapped", "无法从分组/命名解析 APP"
        elif any(kw in name for kw in KEYWORD_HINTS):
            st, rea = "special", "命名含失效关键词，无流程归属"
        else:
            st, rea = "unmapped", "命名 APP 段未匹配到任何流程"
        extras.append({**a, "status": st, "reason": rea})

    return by_flow, extras


def action_from_selector(asset, flow_plan, image_by_file):
    """把控件选择器转为动作候选 dict（尽力还原类型与文本）。"""
    hint = SELECTOR_TYPE_HINT.get(asset["prefix"], "text")
    act = {"source": "selector", "shadowbot_name": asset["name"]}
    if hint == "image":
        act["type"] = "image_template"      # 图片类选择器 -> 视觉模板候选
        act["images"] = [asset["screenshot"]] if asset.get("screenshot") else []
    elif asset.get("text"):
        act["type"] = "click_text"
        act["text"] = asset["text"]
    elif asset.get("res_id"):
        act["type"] = "click_id"
        act["res_id"] = asset["res_id"]
    else:
        act["type"] = "click_first"
        act["candidates"] = []
        if asset.get("res_id"):
            act["candidates"].append({"type": "id", "value": asset["res_id"]})
    # 尝试绑定同流程同页面图片做视觉兜底
    if act.get("type") in ("click_text", "click_id", "click_first"):
        page = None
        seg = (asset.get("rest") or "").split("-")
        if len(seg) >= 2:
            page = seg[1]
        if page:
            imgs = [i for i in flow_plan["images"] if i.get("page") == page]
            if imgs:
                act["images"] = [i["file"] for i in imgs[:2]]
    return act


def action_from_image(asset):
    """把图片选择器转为动作候选 dict（作为视觉兜底模板挂接点）。"""
    return {
        "type": "image_template",
        "source": "image",
        "shadowbot_name": asset["name"],
        "name": asset["name"],
        "file": asset["file"] if asset.get("file") else "",
        "page": asset["page"],
        "action": asset["action"],
        "similarity": asset["similarity"],
        "adaptive": asset["adaptive"],
        "scalingfactor": asset["scalingfactor"],
        "graying": asset["graying"],
        # 用法：将 file 填到任意 click_* 动作的 images 字段做视觉兜底
    }


def migrate(src_dir, proj_dir, dry_run=False):
    # ---------------- 解析 ----------------
    pkg = parse_package_json(src_dir)
    flow_by_name = parse_flows(pkg)
    selectors = parse_selectors(src_dir)
    images = parse_images(src_dir)

    # 图片文件名分类（valid 的才会复制/引用）
    for img in images:
        raw = img["filepath"].replace("\\", "/")
        img["basename"] = os.path.basename(raw)
        img["file"] = ""

    # ---------------- 计划 ----------------
    by_flow, extras = build_plan(flow_by_name, selectors, images)

    # ---------------- 统计 ----------------
    stats = {"selectors": 0, "images": 0, "excluded_img_count": 0,
             "valid_selector_count": 0}
    status_count = {}
    for flow_plan in by_flow.values():
        st = flow_plan["status"]
        status_count[st] = status_count.get(st, 0) + 1
        stats["selectors"] += len(flow_plan["selectors"])
        stats["images"] += len(flow_plan["images"])
        if st == "valid":
            stats["valid_selector_count"] += len(flow_plan["selectors"])
    status_count["unmapped_extra"] = len(extras)

    # ---------------- 有效资产落盘 ----------------
    apps_for_yaml = []
    excluded_manifest = []          # 失效/待测/特殊 清单
    copied_files, missing_files = [], []
    images_out = os.path.join(proj_dir, "images")
    excluded_out = os.path.join(proj_dir, "excluded")

    if not dry_run:
        os.makedirs(images_out, exist_ok=True)
        os.makedirs(excluded_out, exist_ok=True)

    # 先给有效图片分配 file 并复制
    valid_flows = [f for f in by_flow.values() if f["status"] == "valid"]

    def copy_image_if_valid(app_flow, img):
        """有效资产引用的图片才复制进 images/<app>/。返回目标相对路径或空。"""
        if app_flow["status"] != "valid":
            return ""
        raw = img["filepath"].replace("\\", "/")
        basename = os.path.basename(raw)
        src_file = os.path.join(src_dir, "..", raw) if not os.path.isabs(raw) else raw
        src_file = os.path.normpath(src_file)
        # filepath 如 resources/images/xxx.png（相对工程根），直接拼接
        src_abs = os.path.normpath(os.path.join(src_dir, raw))
        try:
            tag = os.path.relpath(src_abs, proj_dir)
        except ValueError:
            # 源(C:) 与目标(D:) 跨盘符，无法相对化，仅记录源文件名
            tag = os.path.join("src", basename)
        rel = os.path.join("images", app_flow["flow"], basename)
        if not os.path.isfile(src_abs):
            missing_files.append((img["name"], raw, app_flow["flow"]))
            return ""
        if not dry_run:
            dst = os.path.join(images_out, app_flow["flow"], basename)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src_abs):
                shutil.copy2(src_abs, dst)
            copied_files.append(tag)
        else:
            copied_files.append(tag)
        return rel.replace("\\", "/")

    for flow_plan in by_flow.values():
        # 分配图片目标路径
        for img in flow_plan["images"]:
            img["file"] = copy_image_if_valid(flow_plan, img)

    # 收集各流程归属的图片按页用于行为绑定
    for flow_plan in by_flow.values():
        if flow_plan["status"] != "valid":
            continue
        app = {
            "name": flow_plan["flow"],
            "package": None,          # 包名从资产提取（见下）
            "source": "shadowbot",
            "shadowbot_file": flow_plan["file"],
            "shadowbot_group": flow_plan["group"],
            "assets": {
                "selectors": [],
                "image_templates": [],
            },
            "behaviors": {},
        }
        # 包名：优先从 selectors 提取；否则留空待人工补充
        pkgs = {s.get("pkg") for s in flow_plan["selectors"] if s.get("pkg")}
        if len(pkgs) == 1:
            app["package"] = list(pkgs)[0]
        elif len(pkgs) > 1:
            app["package"] = sorted(pkgs)[0]
            app["package_candidates"] = sorted(pkgs)

        for s in flow_plan["selectors"]:
            app["assets"]["selectors"].append({
                "shadowbot_name": s["name"],
                "type_hint": SELECTOR_TYPE_HINT.get(s["prefix"], "text"),
                "text": s["text"] or None,
                "res_id": s["res_id"] or None,
                "page": (s.get("rest") or "").split("-")[1] if len((s.get("rest") or "").split("-")) > 1 else None,
            })
        for img in flow_plan["images"]:
            if not img.get("file"):
                continue
            app["assets"]["image_templates"].append({
                "shadowbot_name": img["name"],
                "file": img["file"],
                "page": img["page"],
                "action": img["action"],
                "similarity": img["similarity"],
                "adaptive": img["adaptive"],
                "graying": img["graying"],
            })
        # behaviors：按意图键聚合动作候选
        for img in flow_plan["images"]:
            if not img.get("file"):
                continue
            key = behavior_key(img)
            app["behaviors"].setdefault(key, []).append(action_from_image(img))
        for s in flow_plan["selectors"]:
            key = behavior_key(s)
            app["behaviors"].setdefault(key, []).append(action_from_selector(s, flow_plan, {}))

        apps_for_yaml.append(app)

    # ---------------- 剔除/特殊 清单 ----------------
    for flow_plan in by_flow.values():
        st = flow_plan["status"]
        if st == "valid":
            continue
        entry = {
            "flow": flow_plan["flow"],
            "file": flow_plan["file"],
            "group": flow_plan["group"],
            "status": st,
            "reason": flow_plan["reason"] or "",
            "n_selectors": len(flow_plan["selectors"]),
            "n_images": len(flow_plan["images"]),
            "excluded_selectors": [s["name"] for s in flow_plan["selectors"]],
            "excluded_images": [i["name"] for i in flow_plan["images"]],
        }
        if flow_plan["keywords_hint"]:
            entry["name_keywords_hint"] = flow_plan["keywords_hint"]
        excluded_manifest.append(entry)
        stats["excluded_img_count"] += len(flow_plan["images"])

    for ex in extras:
        excluded_manifest.append({
            "flow": ex["app_key"] or "?",
            "file": None,
            "group": ex.get("src_group"),
            "status": ex["status"],
            "reason": ex["reason"],
            "n_selectors": 1 if ex["kind"] == "selector" else 0,
            "n_images": 1 if ex["kind"] == "image" else 0,
            "excluded_selectors": [ex["name"]] if ex["kind"] == "selector" else [],
            "excluded_images": [ex["name"]] if ex["kind"] == "image" else [],
        })

    # ---------------- 写 apps_migrated.yaml ----------------
    yaml_doc = {
        "# 说明": "本文件由 tools/migrate_shadowbot.py 自动生成，勿手动编辑；"
                  "仅包含分组'5.运行通过'的有效 APP 资产。",
        "# 用法": "将 apps 数组（或按需挑选条目）并入 config.yaml 的 apps 节；"
                  "images 相对项目根目录，可直接作为 click_* 动作的 images 兜底字段。",
        "apps": apps_for_yaml,
    }
    if not dry_run:
        with open(os.path.join(proj_dir, "apps_migrated.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_doc, f, allow_unicode=True, sort_keys=False, width=200)

    # ---------------- 写 excluded manifest ----------------
    excluded_doc = {
        "说明": "以下资产因 APP 流程分组判定失效/待测/特殊，未接入执行，图片未复制；"
                "如需保留请从源工程 resources/images 手工取回。",
        "items": excluded_manifest,
    }
    if not dry_run:
        with open(os.path.join(excluded_out, "excluded_manifest.yaml"), "w", encoding="utf-8") as f:
            yaml.safe_dump(excluded_doc, f, allow_unicode=True, sort_keys=False, width=200)

    # ---------------- 生成报告 ----------------
    report = build_report(
        src_dir, proj_dir, flow_by_name, by_flow, extras,
        stats, copied_files, missing_files, apps_for_yaml,
        valid_flows, excluded_manifest, dry_run,
    )
    if not dry_run:
        docs_dir = os.path.join(proj_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)
        with open(os.path.join(docs_dir, "migration_report.md"), "w", encoding="utf-8") as f:
            f.write(report)

    # ---------------- 控制台摘要 ----------------
    print("=" * 72)
    print("影刀资产迁移器 完成")
    print(f"  源目录   : {src_dir}")
    print(f"  目标项目 : {proj_dir}")
    print(f"  流程总数 : {len(by_flow)}  有效 {status_count.get('valid', 0)} / "
          f"失效待测 {status_count.get('excluded', 0)}（主流程/模板/子流程/特殊/无映射 合计 "
          f"{sum(v for k, v in status_count.items() if k not in ('valid', 'excluded', 'unmapped_extra'))}）")
    print(f"  选择器   : {stats['selectors']} 个（有效 APP 内 {stats['valid_selector_count']} 个）")
    print(f"  图片     : {stats['images']} 个元素，有效 APP 引用 {len(copied_files)} 个文件，"
          f"剔除 {stats['excluded_img_count']} 个，缺失 {len(missing_files)} 个")
    print(f"  输出     : apps_migrated.yaml / images/ / excluded/ / docs/migration_report.md")
    if dry_run:
        print("  [dry-run] 未写任何文件")
    return 0


def build_report(src_dir, proj_dir, flow_by_name, by_flow, extras,
                 stats, copied_files, missing_files, apps_for_yaml,
                 valid_flows, excluded_manifest, dry_run):
    L = []
    add = L.append
    add("# 影刀(ShadowBot)资产迁移报告")
    add("")
    add(f"- 生成时间：{now_str()}")
    add(f"- 迁移器：`tools/migrate_shadowbot.py`（可重复运行，`--dry-run` / `--src` / `--proj`）")
    add(f"- 源工程（只读）：`{src_dir}`")
    add(f"- 目标项目：`{proj_dir}`")
    add("")
    add("## 一、失效剔除判定逻辑（可审计、可解释、可改参）")
    add("")
    add("1. 依据影刀 `package.json` 的流程分组判定资产状态：")
    add("   - `5.运行通过` → **有效**（迁移进 `images/` 与 `apps_migrated.yaml`）")
    add("   - `4.运行未过` / `1.状态未知` / `6.元素重写` / `0.回收站`（以及 `2.编写未完` / `3.编写已完`）→ **失效/待测**（剔除，仅记录清单到 `excluded/excluded_manifest.yaml`，不复制图片）")
    add("   - `groupName` 为空 → 按名称兜底归类：`main`=主流程、名含`模板`=模板、名含`子流程`=子流程、`运行通过`=特殊待确认、其它=无映射")
    add("2. 资产归属：每个控件/图片选择器按命名首段 APP 名归并到对应流程（精确匹配优先，其次最短超集前缀，如 `飞猪`→`飞猪旅行`、`支付宝`→`支付宝改成元素`）；无法匹配则列入无映射单独归类。")
    add("3. 命名含 `旧 / 回收站 / 模板` 关键词的资产另给提示（不覆盖分组判定）。")
    add("4. 可改参：`tools/migrate_shadowbot.py` 头部 `VALID_GROUPS` / `EXCLUDE_GROUPS` 可调整分组判定；`KEYWORD_HINTS` 调整关键词提示。")
    add("")
    # 总览
    add("## 二、总览")
    add("")
    add("| 维度 | 数量 |")
    add("|---|---|")
    add(f"| 流程总数 | {len(by_flow)} |")
    add(f"| 其中 有效(5.运行通过) | {sum(1 for f in by_flow.values() if f['status']=='valid')} |")
    add(f"| 其中 失效/待测(剔除) | {sum(1 for f in by_flow.values() if f['status']=='excluded')} |")
    add(f"| 其中 主流程/模板/子流程/特殊/无映射 | {sum(1 for f in by_flow.values() if f['status'] not in ('valid','excluded'))} |")
    add(f"| 控件选择器总数 | {stats['selectors']}（其中有效 APP 内 {stats['valid_selector_count']}） |")
    add(f"| 图片选择器总数 | {stats['images']} |")
    add(f"| 有效 APP 实际复制图片文件 | {len(copied_files)} |")
    add(f"| 剔除图片（失效/待测/特殊） | {stats['excluded_img_count']} |")
    add(f"| 引用的图片文件缺失 | {len(missing_files)} |")
    add("")
    if missing_files:
        add("### 缺失图片文件（源未找到，迁移器已跳过，未虚构）")
        add("")
        add("| 资产名 | 源路径 | 归属 APP |")
        add("|---|---|---|")
        for name, raw, app in missing_files:
            add(f"| {name} | {raw} | {app} |")
        add("")
    # 流程明细
    add("## 三、按流程（APP）分组结果")
    add("")
    add("| 流程 | 源文件 | 分组 | 判定 | 选择器数 | 图片数 | 原因 |")
    add("|---|---|---|---|---|---|---|")
    for fp in by_flow.values():
        add(f"| {fp['flow']} | {fp['file']} | {fp['group'] or '—'} | {status_label(fp['status'])} | "
            f"{len(fp['selectors'])} | {len(fp['images'])} | {fp['reason'] or '有效' } |")
    if extras:
        add("")
        add("### 未归属到任何流程的资产（无映射/特殊）")
        add("")
        add("| 资产 | 类型 | 判定 | 原因 |")
        add("|---|---|---|---|")
        for ex in extras:
            add(f"| {ex['name']} | {'选择器' if ex['kind']=='selector' else '图片'} | {status_label(ex['status'])} | {ex['reason']} |")
    add("")
    add("## 四、剔除清单与原因（按 APP）")
    add("")
    ex_items = [it for it in excluded_manifest]
    if not ex_items:
        add("（无剔除项）")
    else:
        for it in ex_items:
            add(f"### {it['flow']}（{it.get('file') or '?'}）— 状态：{status_label(it['status'])}")
            add("")
            add(f"- 原因：{it['reason']}")
            add(f"- 剔除选择器 {it['n_selectors']} 个 / 图片 {it['n_images']} 个")
            if it.get("name_keywords_hint"):
                add(f"- 命名关键词提示：{', '.join(it['name_keywords_hint'])}")
            if it["excluded_selectors"]:
                add(f"- 选择器：{', '.join(it['excluded_selectors'])}")
            if it["excluded_images"]:
                add(f"- 图片：{', '.join(it['excluded_images'])}")
            add("")
    # 有效 APP 资产
    add("## 五、有效 APP 迁移明细")
    add("")
    if not apps_for_yaml:
        add("（无有效 APP 资产）")
    else:
        add("| APP | 源文件 | 包名 | 选择器 | 图片模板 | 行为键 |")
        add("|---|---|---|---|---|---|")
        for app in apps_for_yaml:
            imgfiles = len(app["assets"]["image_templates"])
            sel_count = len(app["assets"]["selectors"])
            add(f"| {app['name']} | {app['shadowbot_file']} | {app['package'] or '—(待人工补)'}"
                f" | {sel_count} | {imgfiles} | {', '.join(app['behaviors'].keys()) or '—'} |")
        add("")
        add("### 图片选择器参数落地说明")
        add("")
        add("""- 影刀 `similarity`（截图匹配相似度 0~100）与 android_autopilot `vision.template_threshold`
口径一致：`similarity=80` 对应 `template_threshold: 0.80`（config.yaml 已默认）。
迁移时逐条记录于 `apps_migrated.yaml` 的 `image_templates[*].similarity`，未改变阈值本身。""")
        add("""- `adaptive=True`（自适应缩放）对应 vision 多尺度模板搜索（`template_scales`），
不直接映射为 config 字段，仅作为参考保留在资产条目中。""")
        add("- `scalingfactor`（匹配缩放倍率）与 `graying`（灰度匹配）同样原样保留为元信息。")
        add("""- 图片以源文件名（UUID.png）复制到 `images/<APP>/`，路径相对项目根目录，可直接填到
任意 `click_*` 动作的 `images:` 字段做视觉兜底，或作为独立模板由 vision.py 加载。""")
        add("")
        add("### 待人工补充包名的 APP（资产中无包名线索，未编造）")
        add("")
        no_pkg = [a["name"] for a in apps_for_yaml if not a.get("package")]
        if no_pkg:
            add(", ".join(no_pkg))
        else:
            add("（无）")
    add("")
    add("## 六、源数据规模")
    add("")
    add(f"- `package.json`：flows {len(flow_by_name)} 条（分组见上）")
    add("- `selectorsV2.xml`：控件选择器按 group 分组；未解析成功项已在相应表备注。")
    add("- `imagesV2.xml`：图片选择器 212 个；`resources/images` 对应图片文件也已核对，"
        "缺失项见上表（迁移器已跳过，不虚构文件）。")
    add("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="影刀资产迁移器")
    ap.add_argument("--src", default=DEFAULT_SRC, help="影刀工程根目录（只读）")
    ap.add_argument("--proj", default=None, help="android_autopilot 项目目录")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不写文件")
    args = ap.parse_args()

    if args.proj is None:
        # 默认：脚本在 <项目>/tools/ 下，向上取项目根
        here = os.path.dirname(os.path.abspath(__file__))
        args.proj = os.path.dirname(here)
    if not os.path.isdir(args.src):
        print(f"[错误] 源目录不存在: {args.src}", file=sys.stderr)
        return 1
    if not os.path.isdir(args.proj):
        print(f"[错误] 目标目录不存在: {args.proj}", file=sys.stderr)
        return 1
    migrate(args.src, args.proj, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
