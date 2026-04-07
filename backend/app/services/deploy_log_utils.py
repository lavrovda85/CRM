"""Pure helpers for deploy log parsing (no heavy imports)."""


def parse_shas_from_deploy_log(log: str) -> tuple[str | None, str | None]:
    """Extract DEPLOY_PREV_SHA= / DEPLOY_NEW_SHA= markers from deploy.sh output."""
    prev = new = None
    for line in log.splitlines():
        if line.startswith("DEPLOY_PREV_SHA="):
            prev = line.split("=", 1)[-1].strip() or None
        elif line.startswith("DEPLOY_NEW_SHA="):
            new = line.split("=", 1)[-1].strip() or None
    return prev, new
