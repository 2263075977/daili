from pathlib import Path
import json
import re

SOURCES = [
    (
        Path("mihomo/direct.yaml"),
        Path("mihomo/direct.txt"),
        Path("sing-box/private_direct.json"),
    ),
    (
        Path("mihomo/proxy.yaml"),
        Path("mihomo/proxy.txt"),
        Path("sing-box/private_proxy.json"),
    ),
]

item_re = re.compile(r"^\s*-\s*['\"]?([^'\"\s#]+)['\"]?\s*(?:#.*)?$")


def normalize_domain(value: str) -> str:
    value = value.strip()

    # Clash/Mihomo wildcard:
    # +.example.com => example.com
    if value.startswith("+."):
        return value[2:]

    # Old style:
    # .example.com => example.com
    if value.startswith("."):
        return value[1:]

    return value


def convert_file(source: Path, surge_target: Path, sing_box_target: Path):
    if not source.exists():
        print(f"Skip missing file: {source}")
        return

    mode = "suffix"
    surge_rules = []
    seen_surge_rules = set()
    sing_box_rules = {
        "domain": [],
        "domain_suffix": [],
        "domain_keyword": [],
    }
    seen_sing_box_rules = {key: set() for key in sing_box_rules}

    def add_surge_rule(rule: str):
        if rule not in seen_surge_rules:
            seen_surge_rules.add(rule)
            surge_rules.append(rule)

    def add_sing_box_rule(rule_type: str, value: str):
        if value not in seen_sing_box_rules[rule_type]:
            seen_sing_box_rules[rule_type].add(value)
            sing_box_rules[rule_type].append(value)

    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            upper = line.upper()

            if "DOMAIN-KEYWORD" in upper:
                mode = "keyword"
            elif "DOMAIN-SUFFIX" in upper:
                mode = "suffix"
            elif "DOMAIN" in upper:
                mode = "domain"
            else:
                mode = "suffix"

            continue

        match = item_re.match(raw_line)
        if not match:
            continue

        value = match.group(1).strip()
        domain = normalize_domain(value)

        if mode == "keyword":
            add_surge_rule(f"DOMAIN-KEYWORD,{domain}")
            add_sing_box_rule("domain_keyword", domain)
        elif mode == "domain":
            add_surge_rule(f"DOMAIN,{domain}")
            add_sing_box_rule("domain", domain)
        else:
            if value.startswith("+.") or value.startswith("."):
                add_surge_rule(f"DOMAIN-SUFFIX,{domain}")
                add_sing_box_rule("domain_suffix", domain)
            else:
                add_surge_rule(f"DOMAIN,{domain}")
                add_sing_box_rule("domain", domain)

    sing_box_rule = {
        rule_type: values
        for rule_type, values in sing_box_rules.items()
        if values
    }

    surge_target.write_text("\n".join(surge_rules) + "\n", encoding="utf-8")
    print(f"Generated {surge_target} with {len(surge_rules)} rules")

    sing_box_target.write_text(
        json.dumps(
            {
                "version": 2,
                "rules": [sing_box_rule],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"Generated {sing_box_target} with "
        f"{sum(len(values) for values in sing_box_rule.values())} rules"
    )


for source, surge_target, sing_box_target in SOURCES:
    convert_file(source, surge_target, sing_box_target)
