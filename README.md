# nogisync

Sync markdown files from a GitHub repository to Notion pages. Directory structure is preserved as a page hierarchy in Notion. Pages are created or updated based on frontmatter titles.

## Features

- 📁 Preserves directory structure as Notion page hierarchy
- 📂 Supports multiple directories via YAML list, newline, or comma separation
- 📝 Extracts page titles from YAML frontmatter
- 🔗 Adds provenance callouts linking back to the source file on GitHub
- ⚡ Parallel syncing with configurable worker count
- 🔀 Two sync methods: `markdown` (Notion markdown API) or `blocks` (convert to Notion blocks)

## Prerequisites

- A Notion account with admin access to the workspace
- Notion API key ([Get one here](https://www.notion.so/my-integrations))
- GitHub repository containing markdown files
- Notion parent page where the content will be synchronized

## Setup

1. Create a new Notion integration in your workspace
2. Add your Notion API key as a GitHub secret named `NOTION_API_KEY`
3. Share your Notion parent page with the integration
4. Get your Notion parent page ID
5. Configure the action in your workflow

## Usage

### GitHub Action

Add the following workflow to your repository (e.g., `.github/workflows/notion-sync.yml`):

```yaml
name: Sync to Notion
on:
  push:
    branches: [main]
    paths:
      - 'docs/**'
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Sync docs to Notion
        uses: Fencer-Security/nogisync@v1.2.0
        with:
          notion_api_key: ${{ secrets.NOTION_API_KEY }}
          notion_parent_page_id: ${{ secrets.NOTION_PARENT_PAGE_ID }}
          docs_path: 'docs/'
```

Multiple directories can be synced using a YAML list:

```yaml
          docs_path:
            - docs/
            - guides/
```

### CLI

nogisync can also be used directly from the command line:

```bash
nogisync --token $NOTION_API_KEY --parent-page-id $PAGE_ID --path docs/
```

Multiple directories:

```bash
nogisync --token $NOTION_API_KEY --parent-page-id $PAGE_ID --path "docs/,guides/"
```

## Configuration Options

| Input | Description | Required | Default |
| ----- | ----------- | -------- | ------- |
| `notion_api_key` | Notion API key for authentication | Yes | - |
| `notion_parent_page_id` | ID of the parent page in Notion | Yes | - |
| `docs_path` | Path(s) to directories containing markdown files (YAML list, newline-separated, or comma-separated) | Yes | - |
| `sync_method` | Sync method: `markdown` (Notion markdown API) or `blocks` (convert to Notion blocks) | No | `markdown` |
| `fail_on_error` | Fail the action if any page fails to sync | No | `false` |

### Frontmatter

Pages use YAML frontmatter to set the Notion page title:

```markdown
---
title: My Page Title
---

# Content starts here
```

If no frontmatter is present, the filename is used as the title (e.g., `getting-started.md` becomes "Getting Started").

## Example Directory Structure

```text
docs/
├── getting-started/
│   ├── installation.md
│   └── configuration.md
├── guides/
│   ├── basic-usage.md
│   └── advanced-features.md
└── README.md
```

This will create a corresponding structure in Notion:

```text
Parent Page
├── Getting Started
│   ├── Installation
│   └── Configuration
├── Guides
│   ├── Basic Usage
│   └── Advanced Features
└── README
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
