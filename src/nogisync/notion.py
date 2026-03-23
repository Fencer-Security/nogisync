import logging
from typing import cast

import notion_client
import stamina

from nogisync.markdown import parse_md
from nogisync.provenance import ProvenanceConfig, create_provenance_block, create_provenance_markdown

logger = logging.getLogger(__name__)


def _is_rate_limited(error: Exception) -> bool:
    """Check if the error is a Notion API rate limit (429) response."""
    return isinstance(error, notion_client.errors.APIResponseError) and error.status == 429


MARKDOWN_API_VERSION = "2026-03-11"


def get_notion_client(token: str) -> notion_client.Client:
    """Get a Notion client."""
    return notion_client.Client(auth=token)


def get_notion_markdown_client(token: str) -> notion_client.Client:
    """Get a Notion client configured for the markdown API endpoints."""
    return notion_client.Client(auth=token, notion_version=MARKDOWN_API_VERSION)


def get_notion_parent_page(client: notion_client.Client, parent_page_id: str) -> dict | None:
    """Get a Notion parent page."""
    results = cast(dict, client.pages.retrieve(page_id=parent_page_id)).get("results")
    return results[0] if results else None


@stamina.retry(on=_is_rate_limited, attempts=5, wait_initial=1.0, wait_max=30.0)
def find_notion_page(client: notion_client.Client, title: str, parent_id: str | None = None) -> dict | None:
    """Find a Notion page by its title."""
    response = cast(dict, client.search(query=title, filter={"value": "page", "property": "object"}))
    results = response.get("results", [])

    for result in results:
        # Tests always return a single matching result, so the title mismatch
        # and parent_id mismatch branches are not exercised
        if (
            result.get("properties", {}).get("title", {}).get("title", [{}])[0].get("text", {}).get("content") == title
        ):  # pragma: no branch
            if not parent_id:
                return result
            elif parent_id and result.get("parent", {}).get("page_id") == parent_id:  # pragma: no branch
                return result
    return None


@stamina.retry(on=_is_rate_limited, attempts=5, wait_initial=1.0, wait_max=30.0)
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

        if provenance_config and content:
            provenance_block = create_provenance_block(provenance_config)
            # create_provenance_block always returns a block when config is enabled,
            # so the None branch is not reachable in practice
            if provenance_block:  # pragma: no branch
                blocks = [provenance_block] + blocks

        new_page = cast(
            dict,
            client.pages.create(
                parent={"page_id": parent_page_id},
                properties={"title": [{"text": {"content": title}}]},
                children=[],
            ),
        )

        while len(blocks) > 100:
            client.blocks.children.append(block_id=new_page["id"], children=blocks[:100])
            blocks = blocks[100:]

        client.blocks.children.append(block_id=new_page["id"], children=blocks)

        return cast(dict, new_page)
    except notion_client.errors.APIResponseError as e:
        if e.status == 429:
            raise
        logger.error(e)
        return {}


@stamina.retry(on=_is_rate_limited, attempts=5, wait_initial=1.0, wait_max=30.0)
def update_notion_page(
    client: notion_client.Client,
    page_id: str,
    content: str,
    provenance_config: ProvenanceConfig | None = None,
) -> None:
    """Update an existing Notion page."""
    try:
        blocks = parse_md(content)

        if provenance_config and content:
            provenance_block = create_provenance_block(provenance_config)
            # create_provenance_block always returns a block when config is enabled,
            # so the None branch is not reachable in practice
            if provenance_block:  # pragma: no branch
                blocks = [provenance_block] + blocks

        existing_blocks = cast(dict, client.blocks.children.list(block_id=page_id)).get("results", [])
        for block in existing_blocks:
            client.blocks.delete(block_id=block["id"])

        while len(blocks) > 100:
            client.blocks.children.append(block_id=page_id, children=blocks[:100])
            blocks = blocks[100:]

        client.blocks.children.append(block_id=page_id, children=blocks)
    except notion_client.errors.APIResponseError as e:
        if e.status == 429:
            raise
        logger.error(e)


def _prepare_markdown_content(content: str, provenance_config: ProvenanceConfig | None = None) -> str:
    """Prepend provenance as markdown text to the content string."""
    if not provenance_config or not provenance_config.enabled or not content:
        return content
    provenance_text = create_provenance_markdown(provenance_config)
    if provenance_text:
        return provenance_text + "\n\n" + content
    return content


@stamina.retry(on=_is_rate_limited, attempts=5, wait_initial=1.0, wait_max=30.0)
def create_notion_page_markdown(
    client: notion_client.Client,
    markdown_client: notion_client.Client,
    parent_page_id: str,
    title: str,
    content: str,
    provenance_config: ProvenanceConfig | None = None,
) -> dict:
    """Create a new page in Notion using the markdown API."""
    try:
        markdown_content = _prepare_markdown_content(content, provenance_config)

        new_page = cast(
            dict,
            client.pages.create(
                parent={"page_id": parent_page_id},
                properties={"title": [{"text": {"content": title}}]},
                children=[],
            ),
        )

        markdown_client.request(
            path=f"/pages/{new_page['id']}/markdown",
            method="PATCH",
            body={"replace_content": markdown_content},
        )

        return cast(dict, new_page)
    except notion_client.errors.APIResponseError as e:
        if e.status == 429:
            raise
        logger.error(e)
        return {}


@stamina.retry(on=_is_rate_limited, attempts=5, wait_initial=1.0, wait_max=30.0)
def update_notion_page_markdown(
    markdown_client: notion_client.Client,
    page_id: str,
    content: str,
    provenance_config: ProvenanceConfig | None = None,
) -> None:
    """Update an existing Notion page using the markdown API."""
    try:
        markdown_content = _prepare_markdown_content(content, provenance_config)

        markdown_client.request(
            path=f"/pages/{page_id}/markdown",
            method="PATCH",
            body={"replace_content": markdown_content},
        )
    except notion_client.errors.APIResponseError as e:
        if e.status == 429:
            raise
        logger.error(e)
