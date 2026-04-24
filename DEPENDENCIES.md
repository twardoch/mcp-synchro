# Dependencies

| Package | Purpose | Why chosen |
|---------|---------|------------|
| fire | CLI framework | Simple, no decorators needed, class-based |
| pydantic | Data validation | v2 models for mcpServers schema, extra="allow" for unknown fields |
| platformdirs | Cross-platform config dirs | Standard solution, well-maintained |
| tomli-w | TOML writing | Lightweight, stdlib tomllib handles reading |
| rich | Console output | Tables, colors, full path display |
| loguru | Logging | Simple API, --verbose mode |
| hatch-vcs | Git-tag versioning | Automatic semver from git tags |
