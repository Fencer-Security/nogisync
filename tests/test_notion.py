from unittest import TestCase
from unittest.mock import MagicMock, patch

import httpx
import notion_client.errors
import stamina

from nogisync.notion import (
    _is_rate_limited,
    create_notion_page,
    find_notion_page,
    get_notion_client,
    get_notion_parent_page,
    update_notion_page,
)
from nogisync.provenance import ProvenanceConfig

stamina.set_testing(True)


def make_api_error(status: int = 400):
    return notion_client.errors.APIResponseError(
        code="rate_limited" if status == 429 else "error",
        status=status,
        message="error",
        headers=httpx.Headers(),
        raw_body_text="",
    )


class TestGetNotionClient(TestCase):
    @patch("notion_client.Client")
    def test_returns_client(self, mock_client):
        client = get_notion_client("test-token")
        mock_client.assert_called_once_with(auth="test-token")
        self.assertIsNotNone(client)


class TestGetNotionParentPage(TestCase):
    def test_returns_first_result(self):
        mock_client = MagicMock()
        mock_client.pages.retrieve.return_value = {"results": [{"id": "page1"}]}
        result = get_notion_parent_page(mock_client, "parent-id")
        self.assertEqual(result, {"id": "page1"})
        mock_client.pages.retrieve.assert_called_once_with(page_id="parent-id")

    def test_returns_none_when_no_results(self):
        mock_client = MagicMock()
        mock_client.pages.retrieve.return_value = {"results": []}
        self.assertIsNone(get_notion_parent_page(mock_client, "parent-id"))

    def test_returns_none_when_results_key_missing(self):
        mock_client = MagicMock()
        mock_client.pages.retrieve.return_value = {}
        self.assertIsNone(get_notion_parent_page(mock_client, "parent-id"))


class TestFindNotionPage(TestCase):
    def setUp(self):
        self.mock_client = MagicMock()

    def test_finds_page_by_title(self):
        self.mock_client.search.return_value = {
            "results": [{"id": "page1", "properties": {"title": {"title": [{"text": {"content": "Test"}}]}}}]
        }
        result = find_notion_page(self.mock_client, "Test")
        self.assertEqual(result["id"], "page1")

    def test_returns_none_when_not_found(self):
        self.mock_client.search.return_value = {"results": []}
        self.assertIsNone(find_notion_page(self.mock_client, "Test"))

    def test_filters_by_parent_id(self):
        self.mock_client.search.return_value = {
            "results": [
                {
                    "id": "page1",
                    "parent": {"page_id": "parent-id"},
                    "properties": {"title": {"title": [{"text": {"content": "Test"}}]}},
                }
            ]
        }
        result = find_notion_page(self.mock_client, "Test", parent_id="parent-id")
        self.assertEqual(result["id"], "page1")
        search_args = self.mock_client.search.call_args[1]
        self.assertEqual(search_args["filter"]["property"], "object")
        self.assertEqual(search_args["filter"]["value"], "page")


class TestCreateNotionPage(TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.pages.create.return_value = {"id": "new-page-id"}

    def test_creates_page_with_blocks(self):
        create_notion_page(self.mock_client, "parent-id", "Title", "Content")
        call_args = self.mock_client.pages.create.call_args[1]
        self.assertEqual(call_args["parent"]["page_id"], "parent-id")
        self.assertEqual(call_args["properties"]["title"][0]["text"]["content"], "Title")

    def test_with_provenance(self):
        config = ProvenanceConfig(enabled=True, include_timestamp=False, file_path="docs/test.md")
        create_notion_page(self.mock_client, "parent-id", "Title", "Content", provenance_config=config)
        children = self.mock_client.blocks.children.append.call_args[1]["children"]
        self.assertEqual(children[0]["type"], "callout")

    def test_with_provenance_disabled(self):
        config = ProvenanceConfig(enabled=False, file_path="docs/test.md")
        create_notion_page(self.mock_client, "parent-id", "Title", "Content", provenance_config=config)
        children = self.mock_client.blocks.children.append.call_args[1]["children"]
        if children:
            self.assertNotEqual(children[0].get("type"), "callout")

    def test_empty_content_skips_provenance(self):
        config = ProvenanceConfig(enabled=True, file_path="docs/test.md")
        create_notion_page(self.mock_client, "parent-id", "Title", "", provenance_config=config)
        children = self.mock_client.blocks.children.append.call_args[1]["children"]
        self.assertEqual(len(children), 0)

    def test_batches_blocks_over_100(self):
        content = "\n".join(f"Line {i}" for i in range(150))
        result = create_notion_page(self.mock_client, "parent-id", "Title", content)
        self.assertEqual(result, {"id": "new-page-id"})
        append_calls = self.mock_client.blocks.children.append.call_args_list
        self.assertEqual(len(append_calls), 2)
        self.assertEqual(len(append_calls[0][1]["children"]), 100)
        self.assertEqual(len(append_calls[1][1]["children"]), 50)

    def test_returns_empty_dict_on_api_error(self):
        self.mock_client.pages.create.side_effect = make_api_error()
        result = create_notion_page(self.mock_client, "parent-id", "Title", "content")
        self.assertEqual(result, {})


class TestUpdateNotionPage(TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.mock_client.blocks.children.list.return_value = {"results": []}

    def test_updates_page(self):
        update_notion_page(self.mock_client, "page-id", "Content")
        call_args = self.mock_client.blocks.children.append.call_args[1]
        self.assertEqual(call_args["block_id"], "page-id")
        self.assertIn("children", call_args)

    def test_with_provenance(self):
        config = ProvenanceConfig(enabled=True, include_timestamp=False, file_path="docs/test.md")
        update_notion_page(self.mock_client, "page-id", "Content", provenance_config=config)
        children = self.mock_client.blocks.children.append.call_args[1]["children"]
        self.assertEqual(children[0]["type"], "callout")

    def test_deletes_existing_blocks(self):
        self.mock_client.blocks.children.list.return_value = {
            "results": [
                {"id": "old-block-1", "type": "callout"},
                {"id": "old-block-2", "type": "paragraph"},
            ]
        }
        config = ProvenanceConfig(enabled=True, include_timestamp=False, file_path="docs/test.md")
        update_notion_page(self.mock_client, "page-id", "Content", provenance_config=config)
        self.assertEqual(self.mock_client.blocks.delete.call_count, 2)

    def test_batches_blocks_over_100(self):
        content = "\n".join(f"Line {i}" for i in range(150))
        update_notion_page(self.mock_client, "page-id", content)
        append_calls = self.mock_client.blocks.children.append.call_args_list
        self.assertEqual(len(append_calls), 2)
        self.assertEqual(len(append_calls[0][1]["children"]), 100)
        self.assertEqual(len(append_calls[1][1]["children"]), 50)

    def test_handles_api_error(self):
        self.mock_client.blocks.children.list.side_effect = make_api_error()
        update_notion_page(self.mock_client, "page-id", "content")


class TestIsRateLimited(TestCase):
    def test_returns_true_for_429(self):
        self.assertTrue(_is_rate_limited(make_api_error(status=429)))

    def test_returns_false_for_other_status(self):
        self.assertFalse(_is_rate_limited(make_api_error(status=400)))

    def test_returns_false_for_non_api_error(self):
        self.assertFalse(_is_rate_limited(ValueError("not an API error")))


class TestRateLimitRetry(TestCase):
    def test_create_reraises_429(self):
        mock_client = MagicMock()
        mock_client.pages.create.side_effect = make_api_error(status=429)
        with self.assertRaises(notion_client.errors.APIResponseError):
            create_notion_page(mock_client, "parent-id", "Title", "content")

    def test_update_reraises_429(self):
        mock_client = MagicMock()
        mock_client.blocks.children.list.side_effect = make_api_error(status=429)
        with self.assertRaises(notion_client.errors.APIResponseError):
            update_notion_page(mock_client, "page-id", "content")
