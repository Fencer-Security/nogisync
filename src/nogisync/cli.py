import logging
from pathlib import Path

import click
import yaml
from frontmatter import Frontmatter

from nogisync import notion
from nogisync.provenance import ProvenanceConfig

logger = logging.getLogger(__name__)


def process_page_hierarchy(client, base_parent_id: str, relative_path: Path) -> str:
    """Creates/updates page hierarchy based on directory structure"""
    current_parent_id = base_parent_id
    path_parts = relative_path.parts[:-1]  # Exclude the markdown file itself

    for part in path_parts:
        # Convert directory name to title case (e.g., "foo_lives_here" -> "Foo Lives Here")
        page_title = " ".join(word.capitalize() for word in part.replace("-", "_").split("_"))

        # Check if page exists under current parent
        existing_page = notion.find_notion_page(client, page_title, parent_id=current_parent_id)

        if existing_page:
            current_parent_id = existing_page["id"]
        else:
            # Create new parent page
            new_page = notion.create_notion_page(client, current_parent_id, page_title, "")
            if new_page:
                current_parent_id = new_page["id"]
            else:
                raise Exception(f"Failed to create new parent page: {page_title}")

    return current_parent_id


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
def main(
    token: str,
    parent_page_id: str,
    path: Path,
    provenance: bool,
    provenance_source_url: str | None,
    provenance_timestamp: bool,
) -> None:
    """
    Sync GitHub markdown files to Notion
    """
    # Use rglob to recursively find all markdown files
    markdown_files = list(Path(path).rglob("*.md"))

    for md_file in markdown_files:
        # Get relative path from source directory
        relative_path = md_file.relative_to(path)

        # Read the markdown file
        try:
            post = Frontmatter.read_file(md_file)
        except yaml.YAMLError:
            logger.info("No valid frontmatter in %s, treating as plain markdown", md_file.name)
            post = {}
        title = get_title(md_file, post)
        content = get_content(md_file, post)

        print(f"Processing {relative_path}...")

        client = notion.get_notion_client(token)

        # Process directory hierarchy and get the immediate parent page ID
        immediate_parent_id = process_page_hierarchy(client, parent_page_id, relative_path)

        # Create provenance config for this file
        provenance_config = ProvenanceConfig.from_environment(
            enabled=provenance,
            source_url=provenance_source_url,
            include_timestamp=provenance_timestamp,
            file_path=str(relative_path),
        )

        # Check if page exists under its immediate parent
        existing_page = notion.find_notion_page(client, title, parent_id=immediate_parent_id)

        if existing_page:
            print(f"Updating existing page: {title}")
            notion.update_notion_page(client, existing_page["id"], content, provenance_config)
        else:
            print(f"Creating new page: {title}")
            notion.create_notion_page(client, immediate_parent_id, title, content, provenance_config)


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


if __name__ == "__main__":
    main()
