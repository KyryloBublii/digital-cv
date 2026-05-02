import re


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse a YAML frontmatter block.

    Returns a (fields, body) tuple where fields is a dict of parsed
    key/value pairs and body is the remainder of the document.
    """
    text = _normalize(text)
    if not text.startswith("---\n"):
        return {}, text

    close = text.find("\n---", 4)
    if close == -1:
        return {}, text

    fm_block = text[4:close]
    body = text[close + 4:].lstrip("\n")
    fields: dict = {}
    lines = fm_block.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        if not line.strip() or ":" not in line:
            i += 1
            continue

        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        if val.startswith("[") and val.endswith("]"):
            fields[key] = [
                x.strip().strip("\"'")
                for x in val[1:-1].split(",")
                if x.strip()
            ]
        elif val == "":
            items = []
            j = i + 1
            while j < len(lines) and re.match(r"^\s*-\s+", lines[j]):
                items.append(re.sub(r"^\s*-\s+", "", lines[j]).strip())
                j += 1
            if items:
                fields[key] = items
                i = j
                continue
            else:
                fields[key] = ""
        else:
            fields[key] = val

        i += 1

    return fields, body


def extract_description(body: str) -> str:
    """Return the first plain-text paragraph from the 'What is it' section,
    or fall back to the first non-heading paragraph in the document."""
    match = re.search(
        r"^##\s+What is it\b[^\n]*\n([\s\S]*?)(?=\n##|\Z)",
        body,
        re.MULTILINE,
    )
    source = match.group(1) if match else body

    for block in source.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        block = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", block)
        block = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", block)
        block = re.sub(r"[*_`]", "", block)
        block = re.sub(r"^[-*+]\s+", "", block, flags=re.MULTILINE)
        block = " ".join(block.split())
        if block:
            return block

    return ""
