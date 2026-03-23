import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click
import yaml

from nogisync import notion
from nogisync.provenance import ProvenanceConfig

logger = logging.getLogger(__name__)


def process_page_hierarchy(
    client,
    base_parent_id: str,
    relative_path: Path,
    hierarchy_cache: dict[str, str] | None = None,
) -> str:
    """Creates/updates page hierarchy based on directory structure.

    Uses hierarchy_cache to avoid redundant API lookups when multiple files
    share the same parent directories.
    """
    if hierarchy_cache is None:
        hierarchy_cache = {}

    current_parent_id = base_parent_id
    path_parts = relative_path.parts[:-1]  # Exclude the markdown file itself

    for i, part in enumerate(path_parts):
        cache_key = "/".join(path_parts[: i + 1])
        if cache_key in hierarchy_cache:
            current_parent_id = hierarchy_cache[cache_key]
            continue

        page_title = " ".join(word.capitalize() for word in part.replace("-", "_").split("_"))
        existing_page = notion.find_notion_page(client, page_title, parent_id=current_parent_id)

        if existing_page:
            current_parent_id = existing_page["id"]
        else:
            new_page = notion.create_notion_page(client, current_parent_id, page_title, "")
            if new_page:
                current_parent_id = new_page["id"]
            else:
                raise Exception(f"Failed to create new parent page: {page_title}")

        hierarchy_cache[cache_key] = current_parent_id

    return current_parent_id


def sync_file(
    client,
    md_file: Path,
    path: Path,
    parent_page_id: str,
    provenance: bool,
    provenance_source_url: str | None,
    provenance_timestamp: bool,
    sync_method: str = "blocks",
    markdown_client=None,
) -> None:
    """Sync a single markdown file to Notion."""
    relative_path = md_file.relative_to(path)
    start = time.monotonic()
    logger.info("Started syncing %s", relative_path)

    try:
        post = read_frontmatter(md_file)
    except yaml.YAMLError:
        logger.info("No valid frontmatter in %s, treating as plain markdown", md_file.name)
        post = {}

    title = get_title(md_file, post)
    content = get_content(md_file, post)

    provenance_config = ProvenanceConfig.from_environment(
        enabled=provenance,
        source_url=provenance_source_url,
        include_timestamp=provenance_timestamp,
        file_path=str(relative_path),
    )

    existing_page = notion.find_notion_page(client, title, parent_id=parent_page_id)

    if existing_page:
        logger.info("Updating existing page: %s", title)
        if sync_method == "markdown":
            notion.update_notion_page_markdown(markdown_client, existing_page["id"], content, provenance_config)
        else:
            notion.update_notion_page(client, existing_page["id"], content, provenance_config)
    else:
        logger.info("Creating new page: %s", title)
        if sync_method == "markdown":
            notion.create_notion_page_markdown(
                client, markdown_client, parent_page_id, title, content, provenance_config
            )
        else:
            notion.create_notion_page(client, parent_page_id, title, content, provenance_config)

    elapsed = time.monotonic() - start
    logger.info("Finished syncing %s (%.1fs)", relative_path, elapsed)


@click.command()
@click.option("--token", "-t", type=str, help="Notion API token")
@click.option("--parent-page-id", "-parentid", type=str, help="Notion parent page ID")
@click.option(
    "--path",
    "-p",
    type=click.Path(exists=True, file_okay=False, readable=True, resolve_path=True, path_type=Path),
    help="Path to the markdown files",
)
@click.option(
    "--provenance/--no-provenance",
    default=True,
    help="Enable/disable provenance callout (default: enabled)",
)
@click.option(
    "--provenance-source-url",
    type=str,
    default=None,
    help="Base URL for source files (e.g., https://github.com/org/repo/blob/main)",
)
@click.option(
    "--provenance-timestamp/--no-provenance-timestamp",
    default=True,
    help="Include sync timestamp in provenance (default: enabled)",
)
@click.option(
    "--sync-method",
    type=click.Choice(["blocks", "markdown"], case_sensitive=False),
    default="blocks",
    help="Sync method: 'blocks' (convert to Notion blocks) or 'markdown' (use Notion markdown API)",
)
@click.option(
    "--workers",
    "-w",
    type=int,
    default=4,
    help="Number of parallel workers (default: 4)",
)
def main(
    token: str,
    parent_page_id: str,
    path: Path,
    provenance: bool,
    provenance_source_url: str | None,
    provenance_timestamp: bool,
    sync_method: str,
    workers: int,
) -> None:
    """
    Sync GitHub markdown files to Notion
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    markdown_files = list(Path(path).rglob("*.md"))
    logger.info("Found %d markdown files to sync", len(markdown_files))
    start = time.monotonic()

    client = notion.get_notion_client(token)
    markdown_client = notion.get_notion_markdown_client(token) if sync_method == "markdown" else None

    # Pre-resolve directory hierarchies sequentially (they depend on parent IDs)
    hierarchy_cache: dict[str, str] = {}
    for md_file in markdown_files:
        relative_path = md_file.relative_to(path)
        process_page_hierarchy(client, parent_page_id, relative_path, hierarchy_cache)

    # Build a map of each file to its resolved parent page ID
    file_parent_ids: dict[Path, str] = {}
    for md_file in markdown_files:
        relative_path = md_file.relative_to(path)
        dir_key = str(relative_path.parent)
        file_parent_ids[md_file] = hierarchy_cache.get(dir_key, parent_page_id)

    # Sync files in parallel
    failed = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                sync_file,
                client,
                md_file,
                path,
                file_parent_ids[md_file],
                provenance,
                provenance_source_url,
                provenance_timestamp,
                sync_method,
                markdown_client,
            ): md_file
            for md_file in markdown_files
        }
        for future in as_completed(futures):
            md_file = futures[future]
            try:
                future.result()
            except Exception:
                logger.exception("Failed to sync %s", md_file.relative_to(path))
                failed.append(md_file)

    elapsed = time.monotonic() - start
    logger.info("Sync complete: %d files in %.1fs (%d failed)", len(markdown_files), elapsed, len(failed))


_FRONTMATTER_RE = re.compile(r"^\s*(?:---|\+\+\+)(.*?)(?:---|\+\+\+)\s*(.+)$", re.DOTALL)


def read_frontmatter(path: Path) -> dict:
    """Read a markdown file and split YAML frontmatter from body."""
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.search(text)
    if not match:
        return {"attributes": None, "body": text}
    return {
        "attributes": yaml.load(match.group(1), Loader=yaml.SafeLoader),
        "body": match.group(2),
    }


def get_content(md_file: Path, post: dict) -> str:
    content = post.get("body")
    if not content:
        with open(md_file, "r") as f:
            content = f.read()
    return content


def get_title(md_file: Path, post: dict) -> str:
    if post.get("attributes"):
        return post.get("attributes", {}).get("title", md_file.stem)
    else:
        return " ".join(word.capitalize() for word in md_file.stem.replace("-", "_").split("_"))


# Entry point only used when running the module directly, not during tests
if __name__ == "__main__":  # pragma: no cover
    main()
