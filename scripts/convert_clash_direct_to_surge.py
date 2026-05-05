from pathlib import Path
import re

SOURCES = [
    Path("mihomo/direct.yaml"),
    Path("mihomo/proxy.yaml"),
]

item_re = re.compile(r"^\s*-\s*['\"]?([^'\"\s#]+)['\"]?\s*(?:#.*)?$")


def convert_file(source: Path):
    target = source.with_suffix(".txt")

    if not source.exists():
        print(f"Skip missing file: {source}")
        return

    mode = "suffix"
    rules = []
    seen = set()

    def add_rule(rule: str):
        if rule not in seen:
            seen.add(rule)
            rules.append(rule)

    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            upper = line.upper()
            if "DOMAIN-KEYWORD" in upper:
                mode = "keyword"
            elif "DOMAIN" in upper:
                mode = "domain"
            else:
                mode = "suffix"
            continue

        match = item_re.match(raw_line)
        if not match:
            continue

        value = match.group(1).strip()

        if mode == "keyword":
            add_rule(f"DOMAIN-KEYWORD,{value.lstrip('.')}")
        elif mode == "domain":
            add_rule(f"DOMAIN,{value.lstrip('.')}")
        else:
            if value.startswith("."):
                add_rule(f"DOMAIN-SUFFIX,{value.lstrip('.')}")
            else:
                add_rule(f"DOMAIN,{value}")

    target.write_text("\n".join(rules) + "\n", encoding="utf-8")
    print(f"Generated {target} with {len(rules)} rules")


for source in SOURCES:
    convert_file(source)
