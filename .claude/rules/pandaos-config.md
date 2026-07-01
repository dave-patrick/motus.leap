# PandaOS Configuration

This project is managed by PandaOS.

All rules live in `.claude/rules/`. Knowledge files use a `knowledge-` prefix, principles use `principle-`.

## User Profile
- **Name:** Dave
- **Expertise:** explorer

The user has moderate technical understanding. You can mention technical concepts but explain them briefly. Show key code snippets when relevant but don't deep-dive into implementation details unprompted. Balance clarity with enough technical context to be informative.

## Browser Tools
This project has the **PandaOS embedded browser** enabled (`pandaos-browser` MCP). When multiple browser MCPs are available (e.g. `chrome-devtools`, `playwright`), **always prefer `pandaos-browser` tools** (`browser_navigate`, `browser_click`, `browser_screenshot`, etc.) over external browser tools. The embedded browser runs inside PandaOS without opening an external window.

## Visualizations

When the goal is to *show the user something visual*, pick one of these options — do not write throwaway HTML files into the project just to display something. (Writing an actual HTML file is correct when the HTML is the deliverable itself: part of a static site, a docs example, a tool that lives in the repo, or whenever the user explicitly asks for a file.)

- **Inline visualizations** — ` ```html ` code blocks render as live interactive visuals directly in the chat. Use for small, glanceable output: simple comparisons, sparklines, compact diagrams, single KPI cards. Hard rules: must fit in ~250px tall with no scrolling, self-contained snippet (no `<html>`/`<body>` tags), transparent background only (never set `background` on body/html/outer container), use `color: inherit` (never hardcode text colors like `#fff` — breaks on the other theme), CDN imports OK, under 50KB.
- **Artifacts** — page-shaped HTML the user iterates on. Use for mockups, landing pages, dashboards, and anything worth versioning, tweaking, or sharing. Call `artifact_get_design_system` first to inherit the project palette, then `artifact_create`. The artifact opens in a sandboxed preview with live theme controls; subsequent edits go through `artifact_edit` or `artifact_regenerate`.

How to pick:
- glanceable, fits in chat: use an inline visualization
- page-shaped, the user will iterate on it: use an artifact

When the user asks about PandaOS features or settings, use the `pandaos_docs_search` tool.

## Connected Apps

The following apps are authenticated and have MCP tools available. Use `ToolSearch` to find their tools before falling back to other approaches.

- **pandaos-docs** (`pandaos-docs`) - 3 tools
- **skills** (`skills`) - 5 tools
- **Slides** (`slides`) - 6 tools
- **Git** (`git`) - 9 tools
- **credentials** (`credentials`) - 6 tools
- **Artifacts** (`artifacts`) - 12 tools
- **automations** (`automations`) - 3 tools
- **agent-signals** (`agent-signals`) - 2 tools
- **pandaos-navigation** (`pandaos-navigation`) - 1 tools
- **devserver** (`devserver`) - 3 tools

## Team Members

You have team members available for this project. **Delegate work to the right
specialist** — do not do their job yourself when a team member has the expertise.
Only handle trivial work directly (typo fixes, one-line config changes, quick answers).
For anything substantial, invoke the appropriate team member(s).

**Before starting work**, read `.pandaos/config.yaml` for project paths, code quality
limits, and other settings. Each team member lists their skills — use them.

**Skills are mandatory.** When a team member has skills listed, they MUST invoke
the relevant skill for each matching task. Skills contain the methodology — the
agent provides the persona and workflow, the skill provides the how.

### On-Demand Team Members (Personas — NOT Sub-Agents)

> **These are personas, not separate agents.** Read their instruction file and **adopt their role inline** in this conversation. Do NOT use the Task tool to launch a separate sub-agent for these members.

| Member | When to invoke | Instructions | Skills |
|--------|----------------|--------------|--------|
| planner | Before ANY new feature or non-trivial task — always invoke first | `.pandaos/team/planner.md` | planning-and-task-breakdown, spec-driven-development |
| builder | After planning (and design if UI), to implement the feature | `.pandaos/team/builder.md` | incremental-implementation, ai-code-review, git-commit |
| reviewer | After implementation, to verify quality and correctness before shipping | `.pandaos/team/reviewer.md` | ai-code-review |
| designer | After planning, when the feature has UI that needs design decisions before implementation | `.pandaos/team/designer.md` | frontend-design |

Before starting any non-trivial task, check the "When to invoke" column above. If the task matches a team member's trigger, adopt that member's persona and follow their instructions.
For ad-hoc questions, quick answers, and tasks that don't match any trigger, respond directly.
