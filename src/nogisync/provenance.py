"""Provenance tracking for synced Notion pages."""

import os
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ProvenanceConfig:
    """Configuration for provenance tracking."""

    enabled: bool = True
    source_url: str | None = None
    include_timestamp: bool = True
    file_path: str | None = None

    @classmethod
    def from_environment(
        cls,
        enabled: bool = True,
        source_url: str | None = None,
        include_timestamp: bool = True,
        file_path: str | None = None,
    ) -> "ProvenanceConfig":
        """Create config with GitHub Actions environment variable detection."""
        if source_url is None:
            # Auto-detect from GitHub Actions environment
            github_repo = os.environ.get("GITHUB_REPOSITORY")
            github_ref = os.environ.get("GITHUB_REF", "")
            github_sha = os.environ.get("GITHUB_SHA")

            if github_repo:
                # Extract branch name from ref (refs/heads/main -> main)
                branch = "main"
                if github_ref.startswith("refs/heads/"):
                    branch = github_ref[len("refs/heads/") :]
                elif github_sha:
                    # Use commit SHA if no branch ref available
                    branch = github_sha

                source_url = f"https://github.com/{github_repo}/blob/{branch}"

        return cls(
            enabled=enabled,
            source_url=source_url,
            include_timestamp=include_timestamp,
            file_path=file_path,
        )


def create_provenance_block(config: ProvenanceConfig) -> dict | None:
    """Create a Notion callout block with provenance information.

    Returns None if provenance is disabled or if this is an empty directory page.
    """
    if not config.enabled:
        return None

    # Build the message parts
    message_parts = ["This page is synced from GitHub. Edits will be overwritten."]

    # Add source file path/URL
    if config.file_path:
        if config.source_url:
            # Full GitHub URL
            full_url = f"{config.source_url.rstrip('/')}/{config.file_path}"
            # Truncate if needed (Notion has 2000 char limit for rich text)
            if len(full_url) > 1900:
                full_url = full_url[:1897] + "..."
            message_parts.append(f"Source: {full_url}")
        else:
            # Relative path only
            source_path = config.file_path
            if len(source_path) > 1900:
                source_path = source_path[:1897] + "..."
            message_parts.append(f"Source: {source_path}")

    # Add timestamp if enabled
    if config.include_timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        message_parts.append(f"Last synced: {timestamp}")

    # Join with newlines
    message = "\n".join(message_parts)

    return {
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": message}}],
            "icon": {"type": "emoji", "emoji": "\u26a0\ufe0f"},
            "color": "yellow_background",
        },
    }


def _build_provenance_message_parts(config: ProvenanceConfig) -> list[str] | None:
    """Build provenance message parts shared by both block and markdown formats.

    Returns None if provenance is disabled.
    """
    if not config.enabled:
        return None

    message_parts = ["This page is synced from GitHub. Edits will be overwritten."]

    if config.file_path:
        if config.source_url:
            full_url = f"{config.source_url.rstrip('/')}/{config.file_path}"
            if len(full_url) > 1900:
                full_url = full_url[:1897] + "..."
            message_parts.append(f"Source: {full_url}")
        else:
            source_path = config.file_path
            if len(source_path) > 1900:
                source_path = source_path[:1897] + "..."
            message_parts.append(f"Source: {source_path}")

    if config.include_timestamp:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        message_parts.append(f"Last synced: {timestamp}")

    return message_parts


def create_provenance_markdown(config: ProvenanceConfig) -> str | None:
    """Create an enhanced markdown callout with provenance information.

    Returns None if provenance is disabled.
    """
    parts = _build_provenance_message_parts(config)
    if parts is None:
        return None
    content = "\n".join(f"\t{part}" for part in parts)
    return f'<callout icon="⚠️" color="yellow_bg">\n{content}\n</callout>'
