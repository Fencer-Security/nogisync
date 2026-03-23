import os
from unittest import TestCase
from unittest.mock import patch

from nogisync.provenance import ProvenanceConfig, create_provenance_block, create_provenance_markdown


class TestProvenanceConfig(TestCase):
    def test_default_config(self):
        config = ProvenanceConfig()
        self.assertTrue(config.enabled)
        self.assertIsNone(config.source_url)
        self.assertTrue(config.include_timestamp)
        self.assertIsNone(config.file_path)

    def test_config_with_values(self):
        config = ProvenanceConfig(
            enabled=False,
            source_url="https://github.com/org/repo/blob/main",
            include_timestamp=False,
            file_path="docs/readme.md",
        )
        self.assertFalse(config.enabled)
        self.assertEqual(config.source_url, "https://github.com/org/repo/blob/main")
        self.assertFalse(config.include_timestamp)
        self.assertEqual(config.file_path, "docs/readme.md")

    def test_from_environment_with_explicit_url(self):
        config = ProvenanceConfig.from_environment(
            source_url="https://example.com/repo/blob/main",
            file_path="test.md",
        )
        self.assertEqual(config.source_url, "https://example.com/repo/blob/main")

    @patch.dict(os.environ, {"GITHUB_REPOSITORY": "myorg/myrepo"}, clear=True)
    def test_from_environment_github_repo_only(self):
        config = ProvenanceConfig.from_environment(file_path="test.md")
        self.assertEqual(config.source_url, "https://github.com/myorg/myrepo/blob/main")

    @patch.dict(
        os.environ,
        {"GITHUB_REPOSITORY": "myorg/myrepo", "GITHUB_REF": "refs/heads/develop"},
        clear=True,
    )
    def test_from_environment_github_with_branch(self):
        config = ProvenanceConfig.from_environment(file_path="test.md")
        self.assertEqual(config.source_url, "https://github.com/myorg/myrepo/blob/develop")

    @patch.dict(
        os.environ,
        {"GITHUB_REPOSITORY": "myorg/myrepo", "GITHUB_SHA": "abc123def"},
        clear=True,
    )
    def test_from_environment_github_with_sha(self):
        config = ProvenanceConfig.from_environment(file_path="test.md")
        self.assertEqual(config.source_url, "https://github.com/myorg/myrepo/blob/abc123def")

    @patch.dict(os.environ, {}, clear=True)
    def test_from_environment_no_github_vars(self):
        config = ProvenanceConfig.from_environment(file_path="test.md")
        self.assertIsNone(config.source_url)


class TestCreateProvenanceBlock(TestCase):
    def test_disabled_returns_none(self):
        config = ProvenanceConfig(enabled=False, file_path="test.md")
        result = create_provenance_block(config)
        self.assertIsNone(result)

    def test_basic_provenance_block(self):
        config = ProvenanceConfig(
            enabled=True,
            include_timestamp=False,
            file_path="docs/readme.md",
        )
        result = create_provenance_block(config)

        self.assertIsNotNone(result)
        self.assertEqual(result["type"], "callout")
        self.assertEqual(result["callout"]["icon"]["emoji"], "\u26a0\ufe0f")
        self.assertEqual(result["callout"]["color"], "yellow_background")

        content = result["callout"]["rich_text"][0]["text"]["content"]
        self.assertIn("This page is synced from GitHub", content)
        self.assertIn("Source: docs/readme.md", content)

    def test_provenance_block_with_source_url(self):
        config = ProvenanceConfig(
            enabled=True,
            source_url="https://github.com/org/repo/blob/main",
            include_timestamp=False,
            file_path="docs/readme.md",
        )
        result = create_provenance_block(config)

        content = result["callout"]["rich_text"][0]["text"]["content"]
        self.assertIn("https://github.com/org/repo/blob/main/docs/readme.md", content)

    def test_provenance_block_with_timestamp(self):
        config = ProvenanceConfig(
            enabled=True,
            include_timestamp=True,
            file_path="docs/readme.md",
        )
        result = create_provenance_block(config)

        content = result["callout"]["rich_text"][0]["text"]["content"]
        self.assertIn("Last synced:", content)
        self.assertIn("UTC", content)

    def test_provenance_block_without_file_path(self):
        config = ProvenanceConfig(
            enabled=True,
            include_timestamp=False,
        )
        result = create_provenance_block(config)

        content = result["callout"]["rich_text"][0]["text"]["content"]
        self.assertIn("This page is synced from GitHub", content)
        self.assertNotIn("Source:", content)

    def test_long_file_path_truncation(self):
        long_path = "a" * 2000
        config = ProvenanceConfig(
            enabled=True,
            include_timestamp=False,
            file_path=long_path,
        )
        result = create_provenance_block(config)

        content = result["callout"]["rich_text"][0]["text"]["content"]
        # Content should be truncated
        self.assertLess(len(content), 2100)
        self.assertIn("...", content)

    def test_long_url_truncation(self):
        long_path = "a" * 2000
        config = ProvenanceConfig(
            enabled=True,
            source_url="https://github.com/org/repo/blob/main",
            include_timestamp=False,
            file_path=long_path,
        )
        result = create_provenance_block(config)

        content = result["callout"]["rich_text"][0]["text"]["content"]
        self.assertLess(len(content), 2100)
        self.assertIn("...", content)

    def test_source_url_trailing_slash_handled(self):
        config = ProvenanceConfig(
            enabled=True,
            source_url="https://github.com/org/repo/blob/main/",
            include_timestamp=False,
            file_path="docs/readme.md",
        )
        result = create_provenance_block(config)

        content = result["callout"]["rich_text"][0]["text"]["content"]
        # Should not have double slash
        self.assertIn("main/docs/readme.md", content)
        self.assertNotIn("main//docs", content)


class TestCreateProvenanceMarkdown(TestCase):
    def test_disabled_returns_none(self):
        config = ProvenanceConfig(enabled=False, file_path="test.md")
        result = create_provenance_markdown(config)
        self.assertIsNone(result)

    def test_basic_provenance_markdown(self):
        config = ProvenanceConfig(
            enabled=True,
            include_timestamp=False,
            file_path="docs/readme.md",
        )
        result = create_provenance_markdown(config)

        self.assertIsNotNone(result)
        self.assertTrue(result.startswith('<callout icon="⚠️" color="yellow_bg">'))
        self.assertTrue(result.endswith("</callout>"))
        self.assertIn("\tThis page is synced from GitHub. Edits will be overwritten.", result)
        self.assertIn("\tSource: docs/readme.md", result)

    def test_provenance_markdown_with_source_url(self):
        config = ProvenanceConfig(
            enabled=True,
            source_url="https://github.com/org/repo/blob/main",
            include_timestamp=False,
            file_path="docs/readme.md",
        )
        result = create_provenance_markdown(config)

        self.assertIn("\tSource: https://github.com/org/repo/blob/main/docs/readme.md", result)

    def test_provenance_markdown_with_timestamp(self):
        config = ProvenanceConfig(
            enabled=True,
            include_timestamp=True,
            file_path="docs/readme.md",
        )
        result = create_provenance_markdown(config)

        self.assertIn("\tLast synced:", result)
        self.assertIn("UTC", result)

    def test_provenance_markdown_without_file_path(self):
        config = ProvenanceConfig(
            enabled=True,
            include_timestamp=False,
        )
        result = create_provenance_markdown(config)

        self.assertIn("\tThis page is synced from GitHub", result)
        self.assertNotIn("Source:", result)

    def test_long_url_truncation(self):
        long_path = "a" * 2000
        config = ProvenanceConfig(
            enabled=True,
            source_url="https://github.com/org/repo/blob/main",
            include_timestamp=False,
            file_path=long_path,
        )
        result = create_provenance_markdown(config)

        self.assertIn("...", result)

    def test_long_file_path_truncation(self):
        long_path = "a" * 2000
        config = ProvenanceConfig(
            enabled=True,
            include_timestamp=False,
            file_path=long_path,
        )
        result = create_provenance_markdown(config)

        self.assertIn("...", result)
