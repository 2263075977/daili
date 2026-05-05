from pathlib import Path
import re

SOURCE = Path("mihomo/direct.yaml")
TARGET = SOURCE.with_suffix(".txt")

item_re = re.compile(r"^\s*-\s*['\"]?([^'\"\s#]+)['\"]?\s*(?:#.*)?$")

mode = "suffix"
rules = []
seen = set()

def add_rule(rule: str):
    if rule not in seen:
        seen.add(rule)
        rules.append(rule)

for raw_line in SOURCE.read_text(encoding="utf-8").splitlines():
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
        add_rule(f"DOMAIN-KEYWORD,{value.lstrip('.')},DIRECT")
    elif mode == "domain":
        add_rule(f"DOMAIN,{value.lstrip('.')},DIRECT")
    else:
        if value.startswith("."):
            add_rule(f"DOMAIN-SUFFIX,{value.lstrip('.')},DIRECT")
        else:
            add_rule(f"DOMAIN,{value},DIRECT")

TARGET.write_text("\n".join(rules) + "\n", encoding="utf-8")
print(f"Generated {TARGET} with {len(rules)} rules")
