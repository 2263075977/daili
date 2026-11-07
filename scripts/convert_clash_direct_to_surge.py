#!/usr/bin/env python
"""把 mihomo domain 规则集 yaml 转成下游可用格式，并做一致性校验。

产物：
  mihomo/direct.yaml -> mihomo/direct.txt   (Surge RULE-SET)
  mihomo/proxy.yaml  -> mihomo/proxy.txt    (Surge RULE-SET)
  mihomo/reject.yaml -> mihomo/reject.txt   (Surge RULE-SET)
                     -> adguard/reject.txt  (AdGuard / LocalDNS 侧，DNS 层拦截)

映射：
  '+.example.com' / '.example.com' -> DOMAIN-SUFFIX,example.com
  'example.com'                    -> DOMAIN,example.com
  整行注释 '# DOMAIN-KEYWORD' / '# DOMAIN-SUFFIX' / '# DOMAIN' 可切换后续模式。
adin：adguard 侧统一写成 ||domain^（等价 DOMAIN-SUFFIX，含子域）。

用法：
  python scripts/convert_clash_direct_to_surge.py          # 生成/更新产物
  python scripts/convert_clash_direct_to_surge.py --check  # 只校验产物是否落后于 yaml
  （全程只用 python：Windows 上 python3 只是商店别名，CI/Ubuntu 上 python 由 python-is-python3 提供）

注意（历史 bug）：
  * 模式标记曾用子串匹配，reject.yaml 注释里的 'behavior=domain' 会把模式切成
    domain，使 '+.x' 降级成 DOMAIN,x（只匹配裸域，子域全漏）。现在只认整行标记。
  * '+.' 前缀判定必须在 normalize 之前，否则裸域名会被误升级为 DOMAIN-SUFFIX。
"""

from pathlib import Path
import difflib
import re
import sys

SURGE_SOURCES = [
    Path("mihomo/direct.yaml"),
    Path("mihomo/proxy.yaml"),
    Path("mihomo/reject.yaml"),
]
ADGUARD_SOURCE = Path("mihomo/reject.yaml")
ADGUARD_TARGET = Path("adguard/reject.txt")

ADGUARD_DEFAULT_HEADER = [
    "! 恶意 JS 注入 / 仿冒 CDN 域名（Funnull / RingH23）",
    "! 本文件由 scripts/convert_clash_direct_to_surge.py 从 mihomo/reject.yaml 生成，",
    "! 请勿手改域名列表；改集合请改 mihomo/reject.yaml 后由 GitHub Action 重新生成。",
    "! 用途：LocalDNS 的 AdGuard 引擎（DNS 层拦截，覆盖不经 mihomo 的设备）。",
]

item_re = re.compile(r"^\s*-\s*['\"]?([^'\"\s#]+)['\"]?\s*(?:#.*)?$")
marker_re = re.compile(r"^\s*#\s*(DOMAIN-KEYWORD|DOMAIN-SUFFIX|DOMAIN)\s*(?:[:：].*)?$")
MODES = {"DOMAIN-KEYWORD": "keyword", "DOMAIN-SUFFIX": "suffix", "DOMAIN": "domain"}


def normalize_domain(value: str) -> str:
    if value.startswith("+."):      # Clash/Mihomo wildcard
        return value[2:]
    if value.startswith("."):       # old style
        return value[1:]
    return value


def parse_entries(source: Path) -> list[tuple[str, str]]:
    """返回 [(kind, domain)]，kind ∈ {suffix, domain, keyword}，保持顺序去重。"""
    mode = "suffix"
    entries: list[tuple[str, str]] = []
    seen = set()

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
        domain = normalize_domain(raw)
        wildcard = raw.startswith("+.") or raw.startswith(".")
        if mode == "keyword":
            kind = "keyword"
        elif mode == "domain":
            kind = "domain"
        else:
            kind = "suffix" if wildcard else "domain"

        if (kind, domain) not in seen:
            seen.add((kind, domain))
            entries.append((kind, domain))

    return entries


def render_surge(entries: list[tuple[str, str]]) -> str:
    label = {"suffix": "DOMAIN-SUFFIX", "domain": "DOMAIN", "keyword": "DOMAIN-KEYWORD"}
    return "\n".join(f"{label[kind]},{domain}" for kind, domain in entries) + "\n"


def adguard_header() -> list[str]:
    """默认用仓库里已有的 '!' 注释块，保持人工撰写的依据/取证说明不被覆盖。"""
    if ADGUARD_TARGET.exists():
        header = []
        for line in ADGUARD_TARGET.read_text(encoding="utf-8").splitlines():
            if line.startswith("!"):
                header.append(line.rstrip())
            elif line.strip():
                break
        if header:
            return header
    return list(ADGUARD_DEFAULT_HEADER)


def render_adguard(entries: list[tuple[str, str]]) -> str:
    for kind, domain in entries:
        if kind == "keyword":
            sys.exit(f"ERROR: AdGuard 侧无法等价表达 DOMAIN-KEYWORD={domain}，请改规则或调整映射")
        if kind == "domain":
            print(f"WARN: {domain} 是裸域名规则；AdGuard '||{domain}^' 会连子域一起拦", file=sys.stderr)
    body = [f"||{domain}^" for _, domain in entries]
    return "\n".join(adguard_header() + body) + "\n"


def build_expected() -> dict[Path, str]:
    expected: dict[Path, str] = {}

    for source in SURGE_SOURCES:
        if not source.exists():
            print(f"Skip missing file: {source}")
            continue
        entries = parse_entries(source)
        if not entries:
            sys.exit(f"ERROR: {source} 解析出 0 条规则，拒绝生成空规则集")
        expected[source.with_suffix(".txt")] = render_surge(entries)
        print(f"Parse {source} -> {len(entries)} rules")

    if ADGUARD_SOURCE.exists():
        entries = parse_entries(ADGUARD_SOURCE)
        if not entries:
            sys.exit(f"ERROR: {ADGUARD_SOURCE} 解析出 0 条规则")
        expected[ADGUARD_TARGET] = render_adguard(entries)
        print(f"Parse {ADGUARD_SOURCE} -> {len(entries)} AdGuard rules ({ADGUARD_TARGET})")

    return expected


def verify_sets(expected: dict[Path, str]) -> None:
    """产物 ↔ 源集合 1:1 校验：不允许静默丢域名或多出域名。"""
    def domains(text: str, prefix: str) -> list[str]:
        out = []
        for line in text.splitlines():
            if line.startswith(prefix):
                out.append(line[len(prefix):].rstrip("^"))
        return out

    problems = []
    for source in SURGE_SOURCES:
        target = source.with_suffix(".txt")
        if target not in expected:
            continue
        want = sorted(d for _, d in parse_entries(source))
        got = sorted(domains(expected[target], "DOMAIN,") +
                     domains(expected[target], "DOMAIN-SUFFIX,") +
                     domains(expected[target], "DOMAIN-KEYWORD,"))
        if want != got:
            problems.append(f"{target}: yaml {len(want)} 条 ≠ txt {len(got)} 条")

    surge_reject = Path("mihomo/reject.txt")
    if surge_reject in expected and ADGUARD_TARGET in expected:
        one = sorted(domains(expected[surge_reject], "DOMAIN-SUFFIX,"))
        two = sorted(domains(expected[ADGUARD_TARGET], "||"))
        if one != two:
            problems.append(f"{ADGUARD_TARGET} 与 {surge_reject} 集合不一致: "
                            f"仅 adguard={sorted(set(two)-set(one))} 仅 surge={sorted(set(one)-set(two))}")

    if problems:
        sys.exit("ERROR: 产物一致性校验失败\n  " + "\n  ".join(problems))


def main() -> int:
    expected = build_expected()
    verify_sets(expected)

    check_only = "--check" in sys.argv[1:]

    if check_only:
        drift = []
        for path, text in expected.items():
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != text:
                diff = "".join(difflib.unified_diff(
                    current.splitlines(True), text.splitlines(True),
                    fromfile=f"{path} (committed)", tofile=f"{path} (expected)", n=0))
                drift.append(diff)
        if drift:
            print("".join(drift))
            print("ERROR: 产物落后于 yaml，请运行脚本重新生成并提交", file=sys.stderr)
            return 1
        print("OK: 已提交的产物与 yaml 一致")
        return 0

    for path, text in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        old = path.read_text(encoding="utf-8") if path.exists() else ""
        path.write_text(text, encoding="utf-8")
        state = "unchanged" if old == text else "updated"
        print(f"Generated {path} ({state})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
