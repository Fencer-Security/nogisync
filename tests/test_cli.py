from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from nogisync.cli import get_content, get_title, main, process_page_hierarchy, read_frontmatter, sync_file


class TestGetTitle(TestCase):
    def test_with_frontmatter(self):
        post = {"attributes": {"title": "Test Title"}}
        self.assertEqual(get_title(Path("test_file.md"), post), "Test Title")

    def test_without_frontmatter(self):
        self.assertEqual(get_title(Path("test_file_name.md"), {}), "Test File Name")

    def test_with_empty_attributes(self):
        post = {"attributes": {}}
        self.assertEqual(get_title(Path("test_file.md"), post), "Test File")


class TestGetContent(TestCase):
    def test_with_body(self):
        self.assertEqual(get_content(Path("test.md"), {"body": "Test content"}), "Test content")

    @patch("builtins.open")
    def test_without_body_reads_file(self, mock_open):
        mock_open.return_value.__enter__.return_value.read.return_value = "File content"
        self.assertEqual(get_content(Path("test.md"), {}), "File content")
        mock_open.assert_called_once_with(Path("test.md"), "r")


class TestReadFrontmatter(TestCase):
    def test_with_valid_frontmatter(self):
        with CliRunner().isolated_filesystem():
            Path("test.md").write_text("---\ntitle: Hello\n---\nBody text")
            result = read_frontmatter(Path("test.md"))
        self.assertEqual(result["attributes"]["title"], "Hello")
        self.assertEqual(result["body"], "Body text")

    def test_without_frontmatter(self):
        with CliRunner().isolated_filesystem():
            Path("test.md").write_text("# Just markdown\nNo frontmatter here")
            result = read_frontmatter(Path("test.md"))
        self.assertIsNone(result["attributes"])
        self.assertIn("# Just markdown", result["body"])

    def test_with_invalid_yaml_raises(self):
        import yaml

        with CliRunner().isolated_filesystem():
            Path("test.md").write_text("---\n: invalid: yaml: {{{\n---\nBody")
            with self.assertRaises(yaml.YAMLError):
                read_frontmatter(Path("test.md"))


class TestProcessPageHierarchy(TestCase):
    def test_single_level_returns_base_id(self):
        result = process_page_hierarchy(None, "base_id", Path("file.md"))
        self.assertEqual(result, "base_id")

    @patch("nogisync.notion.find_notion_page")
    @patch("nogisync.notion.create_notion_page")
    def test_creates_new_pages(self, mock_create_page, mock_find_page):
        mock_find_page.return_value = None
        mock_create_page.side_effect = lambda client, parent_id, title, content: {"id": f"new_{title}"}

        result = process_page_hierarchy(None, "base_id", Path("dir1/dir2/file.md"))

        self.assertEqual(mock_create_page.call_count, 2)
        mock_create_page.assert_any_call(None, "base_id", "Dir1", "")
        mock_create_page.assert_any_call(None, "new_Dir1", "Dir2", "")
        self.assertEqual(result, "new_Dir2")

    @patch("nogisync.notion.find_notion_page")
    @patch("nogisync.notion.create_notion_page")
    def test_uses_existing_pages(self, mock_create_page, mock_find_page):
        mock_find_page.side_effect = lambda client, title, parent_id: {"id": f"existing_{title}"}

        result = process_page_hierarchy(None, "base_id", Path("dir1/dir2/file.md"))

        mock_create_page.assert_not_called()
        self.assertEqual(result, "existing_Dir2")

    @patch("nogisync.notion.find_notion_page")
    @patch("nogisync.notion.create_notion_page")
    def test_mixed_existing_and_new(self, mock_create_page, mock_find_page):
        mock_find_page.side_effect = lambda client, title, parent_id: (
            {"id": "existing_dir1"} if title == "Dir1" else None
        )
        mock_create_page.side_effect = lambda client, parent_id, title, content: {"id": f"new_{title}"}

        result = process_page_hierarchy(None, "base_id", Path("dir1/dir2/file.md"))

        mock_create_page.assert_called_once_with(None, "existing_dir1", "Dir2", "")
        self.assertEqual(result, "new_Dir2")

    @patch("nogisync.notion.find_notion_page")
    @patch("nogisync.notion.create_notion_page")
    def test_raises_when_page_creation_fails(self, mock_create_page, mock_find_page):
        mock_find_page.return_value = None
        mock_create_page.return_value = None

        with self.assertRaises(Exception, msg="Failed to create new parent page: Dir1"):
            process_page_hierarchy(None, "base_id", Path("dir1/file.md"))

    @patch("nogisync.notion.find_notion_page")
    def test_uses_cache(self, mock_find_page):
        mock_find_page.side_effect = lambda client, title, parent_id: {"id": f"existing_{title}"}
        cache: dict[str, str] = {}

        process_page_hierarchy(None, "base_id", Path("dir1/file1.md"), cache)
        self.assertEqual(mock_find_page.call_count, 1)

        process_page_hierarchy(None, "base_id", Path("dir1/file2.md"), cache)
        self.assertEqual(mock_find_page.call_count, 1)


class TestSyncFile(TestCase):
    @patch("nogisync.cli.notion")
    def test_creates_new_page(self, mock_notion):
        mock_notion.find_notion_page.return_value = None
        mock_notion.create_notion_page.return_value = {"id": "new-page"}

        with CliRunner().isolated_filesystem():
            Path("docs").mkdir()
            Path("docs/test.md").write_text("---\ntitle: Test Doc\n---\nContent")
            sync_file(MagicMock(), Path("docs/test.md"), Path("docs"), "parent-id", True, None, True)

        mock_notion.create_notion_page.assert_called_once()

    @patch("nogisync.cli.notion")
    def test_updates_existing_page(self, mock_notion):
        mock_notion.find_notion_page.return_value = {"id": "existing-page"}

        with CliRunner().isolated_filesystem():
            Path("docs").mkdir()
            Path("docs/test.md").write_text("---\ntitle: Test Doc\n---\nUpdated content")
            sync_file(MagicMock(), Path("docs/test.md"), Path("docs"), "parent-id", True, None, True)

        mock_notion.update_notion_page.assert_called_once()

    @patch("nogisync.cli.notion")
    def test_handles_no_frontmatter(self, mock_notion):
        mock_notion.find_notion_page.return_value = None
        mock_notion.create_notion_page.return_value = {"id": "new-page"}

        with CliRunner().isolated_filesystem():
            Path("docs").mkdir()
            Path("docs/test.md").write_text("# No frontmatter\nJust content")
            sync_file(MagicMock(), Path("docs/test.md"), Path("docs"), "parent-id", True, None, True)

        mock_notion.create_notion_page.assert_called_once()

    @patch("nogisync.cli.notion")
    def test_handles_invalid_yaml_frontmatter(self, mock_notion):
        mock_notion.find_notion_page.return_value = None
        mock_notion.create_notion_page.return_value = {"id": "new-page"}

        with CliRunner().isolated_filesystem():
            Path("docs").mkdir()
            Path("docs/test.md").write_text("---\n: invalid: yaml: {{{\n---\nBody content")
            sync_file(MagicMock(), Path("docs/test.md"), Path("docs"), "parent-id", True, None, True)

        mock_notion.create_notion_page.assert_called_once()


class TestMainFailure(TestCase):
    @patch("nogisync.cli.sync_file", side_effect=RuntimeError("API down"))
    @patch("nogisync.cli.process_page_hierarchy")
    @patch("nogisync.cli.notion")
    def test_logs_and_reports_sync_failures(self, mock_notion, mock_hierarchy, mock_sync):
        runner = CliRunner()
        mock_notion.get_notion_client.return_value = MagicMock()

        with runner.isolated_filesystem():
            Path("docs").mkdir()
            Path("docs/test.md").write_text("content")
            result = runner.invoke(main, ["-t", "fake-token", "-parentid", "parent-id", "-p", "docs"])

        self.assertEqual(result.exit_code, 0)
        mock_sync.assert_called_once()


class TestMain(TestCase):
    @patch("nogisync.cli.notion")
    def test_syncs_files_in_parallel(self, mock_notion):
        runner = CliRunner()
        mock_notion.get_notion_client.return_value = MagicMock()
        mock_notion.find_notion_page.return_value = None
        mock_notion.create_notion_page.return_value = {"id": "new-page"}

        with runner.isolated_filesystem():
            Path("docs").mkdir()
            Path("docs/a.md").write_text("---\ntitle: Doc A\n---\nContent A")
            Path("docs/b.md").write_text("---\ntitle: Doc B\n---\nContent B")
            result = runner.invoke(main, ["-t", "fake-token", "-parentid", "parent-id", "-p", "docs"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(mock_notion.create_notion_page.call_count, 2)

    @patch("nogisync.cli.notion")
    def test_with_subdirectories(self, mock_notion):
        runner = CliRunner()
        mock_notion.get_notion_client.return_value = MagicMock()
        mock_notion.find_notion_page.return_value = None
        mock_notion.create_notion_page.return_value = {"id": "new-page"}

        with runner.isolated_filesystem():
            Path("docs/subdir").mkdir(parents=True)
            Path("docs/subdir/test.md").write_text("---\ntitle: Nested Doc\n---\nContent")
            result = runner.invoke(main, ["-t", "fake-token", "-parentid", "parent-id", "-p", "docs"])

        self.assertEqual(result.exit_code, 0)

    @patch("nogisync.cli.notion")
    def test_with_provenance_disabled(self, mock_notion):
        runner = CliRunner()
        mock_notion.get_notion_client.return_value = MagicMock()
        mock_notion.find_notion_page.return_value = None
        mock_notion.create_notion_page.return_value = {"id": "new-page"}

        with runner.isolated_filesystem():
            Path("docs").mkdir()
            Path("docs/test.md").write_text("---\ntitle: Test Doc\n---\nContent")
            result = runner.invoke(
                main, ["-t", "fake-token", "-parentid", "parent-id", "-p", "docs", "--no-provenance"]
            )

        self.assertEqual(result.exit_code, 0)

    @patch("nogisync.cli.notion")
    def test_custom_workers(self, mock_notion):
        runner = CliRunner()
        mock_notion.get_notion_client.return_value = MagicMock()
        mock_notion.find_notion_page.return_value = None
        mock_notion.create_notion_page.return_value = {"id": "new-page"}

        with runner.isolated_filesystem():
            Path("docs").mkdir()
            Path("docs/test.md").write_text("---\ntitle: Test Doc\n---\nContent")
            result = runner.invoke(main, ["-t", "fake-token", "-parentid", "parent-id", "-p", "docs", "-w", "2"])

        self.assertEqual(result.exit_code, 0)
