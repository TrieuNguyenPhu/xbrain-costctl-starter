"""Shared helpers used by multiple command modules."""


def parse_kv(s):
    """Parse 'key=value' string into a tuple. Raises ValueError on empty key."""
    k, _, v = s.partition("=")
    if not k:
        raise ValueError(f"Invalid key=value pair: {s!r}")
    return k, v


def tags_to_dict(items):
    """Convert boto3 [{'Key':k,'Value':v}, ...] into {k: v, ...}."""
    return {t["Key"]: t["Value"] for t in (items or [])}


def tags_match(tags, want_pairs, missing_keys):
    """Return True iff `tags` matches every (k,v) in want_pairs AND lacks every k in missing_keys."""
    for k, v in want_pairs:
        if tags.get(k) != v:
            return False
    for k in missing_keys:
        if k in tags:
            return False
    return True


def confirm(prompt, force=False):
    """Ask y/N at stdin. Return True only on explicit 'y'."""
    if force:
        return True
    try:
        return input(f"{prompt} [y/N] ").strip().lower() == "y"
    except EOFError:
        return False
