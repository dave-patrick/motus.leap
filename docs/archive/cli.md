# Tube Manager

## Terminal (planned)
- `tube list [--status pending|running|completed|failed]`
- `tube add <title> --type <type> [--priority low|medium|high] [--json <payload>]`
- `tube run <id>`
- `tube remove <id>`

Example flow:
- `tube add "Review PR" --type code --priority high`
- `tube add "Check lights" --type home --json '{"action":"toggle"}'`