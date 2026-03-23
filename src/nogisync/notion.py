import logging
from typing import cast

import notion_client

from nogisync.markdown import parse_md
from nogisync.provenance import ProvenanceConfig, create_provenance_block

logger = logging.getLogger(__name__)


def get_notion_client(token: str) -> notion_client.Client:
    """Get a Notion client."""
    return notion_client.Client(auth=token)


def get_notion_parent_page(client: notion_client.Client, parent_page_id: str) -> dict | None:
    """Get a Notion parent page."""
    results = cast(dict, client.pages.retrieve(page_id=parent_page_id)).get("results")
    return results[0] if results else None


def find_notion_page(client: notion_client.Client, title: str, parent_id: str | None = None) -> dict | None:
    """Find a Notion page by its title."""
    response = cast(dict, client.search(query=title, filter={"value": "page", "property": "object"}))
    results = response.get("results", [])

    for result in results:
        if result.get("properties", {}).get("title", {}).get("title", [{}])[0].get("text", {}).get("content") == title:
            if not parent_id:
                return result
            elif parent_id and result.get("parent", {}).get("page_id") == parent_id:
                return result
    return None


def create_notion_page(
    client: notion_client.Client,
    parent_page_id: str,
    title: str,
    content: str,
    provenance_config: ProvenanceConfig | None = None,
) -> dict:
    """Create a new page in Notion."""
    try:
        blocks = parse_md(content)

        # Prepend provenance block if enabled and content is non-empty
        if provenance_config and content:
            provenance_block = create_provenance_block(provenance_config)
            if provenance_block:
                blocks = [provenance_block] + blocks

        # Create the page
        new_page = cast(
            dict,
            client.pages.create(
                parent={"page_id": parent_page_id},
                properties={"title": [{"text": {"content": title}}]},
                children=[],
            ),
        )

        # Add the blocks to the page
        while len(blocks) > 100:
            client.blocks.children.append(block_id=new_page["id"], children=blocks[:100])
            blocks = blocks[100:]

        client.blocks.children.append(block_id=new_page["id"], children=blocks)

        return cast(dict, new_page)
    except notion_client.errors.APIResponseError as e:
        logger.error(e)
        return {}


def update_notion_page(
    client: notion_client.Client,
    page_id: str,
    content: str,
    provenance_config: ProvenanceConfig | None = None,
) -> None:
    """Update an existing Notion page."""
    try:
        blocks = parse_md(content)

        # Prepend provenance block if enabled and content is non-empty
        if provenance_config and content:
            provenance_block = create_provenance_block(provenance_config)
            if provenance_block:
                blocks = [provenance_block] + blocks

        # First, delete existing blocks
        existing_blocks = cast(dict, client.blocks.children.list(block_id=page_id)).get("results", [])
        for block in existing_blocks:
            client.blocks.delete(block_id=block["id"])

        # Then add new blocks
        while len(blocks) > 100:
            client.blocks.children.append(block_id=page_id, children=blocks[:100])
            blocks = blocks[100:]

        client.blocks.children.append(block_id=page_id, children=blocks)
    except notion_client.errors.APIResponseError as e:
        logger.error(e)
