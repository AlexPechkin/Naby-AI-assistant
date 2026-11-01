# Naby tools catalog · Каталог инструментов Наби · 工具目录

`index.json` — open-source AI tools from GitHub that Naby can connect to a profession or on request
(build 51+). Naby downloads this file once a day; without a network it uses the copy bundled in the build.

## Entry fields

| field | meaning |
|---|---|
| `id` | snake_case, unique |
| `name`, `url` | project name and its GitHub page (only `https://github.com/…`) |
| `purpose`, `value` | what it does; what the profession can do with it that plain chat cannot |
| `integration_kind` | `cli` · `python_package` · `mcp_server` · `app_addon` · `service` · `skill` · `model` |
| `install`, `invoke` | the documented install command and how to call it |
| `professions` | Naby profession ids (`lawyer`, `accountant`, `3d_artist`…) or a group (`legal`, `finance`) |
| `requires`, `platforms`, `risks`, `license`, `stars`, `updated` | as on the project page |
| `verified` | set by the author after a review: only verified entries are offered to a profession automatically |

## How Naby connects a tool

- `skill` → the skill check (injected commands, key theft, download-and-run) → a draft you enable with “approve skill”;
- `mcp_server` → an entry in `mcp.json` after your yes; dangerous server tools ask every time;
- `python_package` → `pip` into a separate environment (binary wheels only) after your yes;
- `cli`, `app_addon`, `service`, `model` → Naby shows the command or the page and what to click; nothing runs by itself.

In Naby: «инструменты» / “tools”, «инструменты для юрист» / “tools for lawyer”, «найди инструмент ocr» / “find tool ocr”,
«инструмент 3» / “tool 3”, «поставь инструмент 3» / “install tool 3”.

## Propose a tool

Open a pull request that adds an entry to `index.json` (or an issue with the GitHub link and the professions it helps).
The author reviews it and sets `verified`. Proposals are data: nothing from a proposal runs before the review.
