#!/usr/bin/env python3
"""把 mihomo 规则集 yaml(behavior=domain) 转成 Surge 可订阅的 txt 规则集。

输入 -> 输出:
  mihomo/direct.yaml -> mihomo/direct.txt
  mihomo/proxy.yaml  -> mihomo/proxy.txt
  mihomo/reject.yaml -> mihomo/reject.txt

映射:
  '+.example.com' / '.example.com' -> DOMAIN-SUFFIX,example.com
  'example.com'                    -> DOMAIN,example.com
  整行注释 '# DOMAIN-KEYWORD' / '# DOMAIN-SUFFIX' / '# DOMAIN' 可切换后续模式。

注意: 模式只认「整行就是标记」的注释。旧实现用子串匹配,
reject.yaml 里 'behavior=domain' 这种正文会把模式切成 domain,
导致 '+.x' 被降级成 DOMAIN,x(只匹配裸域)。
"""

from pathlib import Path
import re
import sys

SOURCES = [
    Path("mihomo/direct.yaml"),
    Path("mihomo/proxy.yaml"),
    Path("mihomo/reject.yaml"),
]

item_re = re.compile(r"^\s*-\s*['\"]?([^'\"\s#]+)['\"]?\s*(?:#.*)?$")
marker_re = re.compile(r"^\s*#\s*(DOMAIN-KEYWORD|DOMAIN-SUFFIX|DOMAIN)\s*(?:[:：].*)?$")
MODES = {"DOMAIN-KEYWORD": "keyword", "DOMAIN-SUFFIX": "suffix", "DOMAIN": "domain"}


def normalize_domain(value: str) -> str:
    value = value.strip()
    if value.startswith("+."):      # Clash/Mihomo wildcard
        return value[2:]
    if value.startswith("."):       # old style
        return value[1:]
    return value


def convert_file(source: Path) -> None:
    target = source.with_suffix(".txt")

    if not source.exists():
        print(f"Skip missing file: {source}")
        return

    mode = "suffix"
    rules = []
    seen = set()

    def add_rule(rule: str) -> None:
        if rule not in seen:
            seen.add(rule)
            rules.append(rule)

    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#"):
            marker = marker_re.match(line)
            if marker:
                mode = MODES[marker.group(1)]
            continue

        match = item_re.match(raw_line)
        if not match:
            continue

        raw = match.group(1).strip()
        value = normalize_domain(raw)
        wildcard = raw.startswith("+.") or raw.startswith(".")
        if mode == "keyword":
            add_rule(f"DOMAIN-KEYWORD,{value}")
        elif mode == "domain":
            add_rule(f"DOMAIN,{value}")
        elif wildcard:
            add_rule(f"DOMAIN-SUFFIX,{value}")
        else:
            add_rule(f"DOMAIN,{value}")

    if not rules:
        print(f"ERROR: {source} 解析出 0 条规则, 拒绝生成空文件", file=sys.stderr)
        sys.exit(1)

    target.write_text("\n".join(rules) + "\n", encoding="utf-8")
    print(f"Generated {target} with {len(rules)} rules")


for source in SOURCES:
    convert_file(source)
