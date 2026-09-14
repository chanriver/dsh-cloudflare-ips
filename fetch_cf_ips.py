#!/usr/bin/env python3
"""
fetch_cf_ips.py
从 api.uouin.com 和 wetest.vip 抓取 Cloudflare 优选 IP，
按规则筛选后输出为 DSH-CFIPS.TXT（格式：IP:PORT）

筛选规则（保持与历史版本一致）：
- 保留线路：电信、多线
- 仅 IPv4
- 端口固定为 443（Cloudflare HTTPS 标准端口）
"""
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import urlopen, Request
from ssl import create_default_context

# 时区：北京时间
CST = timezone(timedelta(hours=8))

# 数据源（通过 Jina Reader 把网页转成 markdown，省去 HTML 解析）
SOURCES = {
    "api.uouin.com": {
        "url": "https://r.jina.ai/https://api.uouin.com/cloudflare.html",
        # 表格行格式：| 序号 | 线路 | 优化IP | 丢包 | 延迟 | 速度 | 带宽 | Colo | 时间 |
        # 例：| 1 | 电信 | 172.64.151.152 | 0.00% | 42.42ms | ...
    },
    "wetest.vip": {
        "url": "https://r.jina.ai/https://www.wetest.vip/page/cloudflare/address_v4.html",
    },
}

# 只保留这些线路
KEEP_LINES = {"电信", "多线"}
PORT = 443
OUTPUT = Path(__file__).parent / "DSH-CFIPS.TXT"

# 匹配 IPv4
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def fetch_markdown(url: str, timeout: int = 30) -> str:
    """通过 Jina Reader 抓取 markdown 内容"""
    req = Request(url, headers={"User-Agent": "DSH-CFIPS/1.0 (+https://github.com/chanriver/dsh-cloudflare-ips)"})
    ctx = create_default_context()
    with urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_uouin(md: str) -> dict[str, list[str]]:
    """
    解析 api.uouin.com 的 markdown 表格。
    表格行：| # | 线路 | 优选IP | 丢包 | 延迟 | 速度 | 带宽 | Colo | 时间 |
    返回 {线路: [ip, ...]}
    """
    result: dict[str, list[str]] = {}
    for line in md.splitlines():
        # 只处理以 | 开头、包含线路关键词的行
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        line_name = cells[1]
        if line_name not in KEEP_LINES:
            continue
        ip_cell = cells[2]
        # IPv4: 4 段数字；IPv6 含冒号会被 IPv4 正则排除
        m = IPV4_RE.fullmatch(ip_cell)
        if not m:
            continue
        ip = m.group(0)
        # 简单校验 IPv4 段值
        if all(0 <= int(p) <= 255 for p in ip.split(".")):
            result.setdefault(line_name, []).append(ip)
    return result


def parse_wetest(md: str) -> dict[str, list[str]]:
    """
    解析 wetest.vip 的 markdown 表格。
    表头：| 线路名称 | 优选地址 | 网络带宽 | 峰值速度 | 往返延迟 | 数据中心 | 更新时间 |
    例：| 移动 | 104.16.248.118 | 5 MB | ...
    返回 {线路: [ip, ...]}
    """
    result: dict[str, list[str]] = {}
    for line in md.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        line_name = cells[0]
        if line_name not in KEEP_LINES:
            continue
        ip_cell = cells[1]
        m = IPV4_RE.fullmatch(ip_cell)
        if not m:
            continue
        ip = m.group(0)
        if all(0 <= int(p) <= 255 for p in ip.split(".")):
            result.setdefault(line_name, []).append(ip)
    return result


def merge_and_dedup(*groups: dict[str, list[str]]) -> dict[str, list[str]]:
    """合并多来源结果并按线路去重 IP（保序）"""
    merged: dict[str, dict[str, None]] = {}
    for g in groups:
        for line, ips in g.items():
            merged.setdefault(line, {})
            for ip in ips:
                merged[line][ip] = None
    return {line: list(ips.keys()) for line, ips in merged.items()}


def render(by_line: dict[str, list[str]], src_counts: dict[str, dict[str, int]]) -> str:
    """生成 TXT 内容"""
    now = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S %z")
    total = sum(len(ips) for ips in by_line.values())
    lines: list[str] = [
        "# DSH-CFIPS.TXT",
        "# Cloudflare 优选 IP 订阅源（电信 + 多线，IPv4 only）",
        "# 数据来源：",
        "#   1. https://api.uouin.com/cloudflare.html",
        "#   2. https://www.wetest.vip/page/cloudflare/address_v4.html",
        f"# 生成时间：{now}",
        f"# IP 总数：{total}（去重后）",
        "# 格式：IP:PORT（端口固定 443，Cloudflare HTTPS 标准端口）",
        "",
    ]

    # 按固定顺序输出
    for line_name in ["电信", "多线"]:
        ips = by_line.get(line_name, [])
        if not ips:
            continue
        lines.append(f"# ----- {line_name} -----")
        lines.extend(f"{ip}:{PORT}" for ip in ips)
        lines.append("")

    # 数据来源统计（附在末尾，便于追溯）
    lines.append("# ----- 数据来源统计 -----")
    for src, counts in src_counts.items():
        lines.append(f"# {src}: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    src_counts: dict[str, dict[str, int]] = {}

    try:
        md_uouin = fetch_markdown(SOURCES["api.uouin.com"]["url"])
        parsed_uouin = parse_uouin(md_uouin)
        src_counts["api.uouin.com"] = {k: len(v) for k, v in parsed_uouin.items()}
        print(f"[ok] api.uouin.com: {parsed_uouin}", file=sys.stderr)
    except Exception as e:
        print(f"[err] api.uouin.com failed: {e}", file=sys.stderr)
        parsed_uouin = {}

    try:
        md_wetest = fetch_markdown(SOURCES["wetest.vip"]["url"])
        parsed_wetest = parse_wetest(md_wetest)
        src_counts["wetest.vip"] = {k: len(v) for k, v in parsed_wetest.items()}
        print(f"[ok] wetest.vip: {parsed_wetest}", file=sys.stderr)
    except Exception as e:
        print(f"[err] wetest.vip failed: {e}", file=sys.stderr)
        parsed_wetest = {}

    if not parsed_uouin and not parsed_wetest:
        print("[fatal] both sources failed, nothing to write", file=sys.stderr)
        return 1

    merged = merge_and_dedup(parsed_uouin, parsed_wetest)
    content = render(merged, src_counts)
    OUTPUT.write_text(content, encoding="utf-8")
    total = sum(len(v) for v in merged.values())
    print(f"[done] wrote {total} IPs to {OUTPUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
