# GitHub credentials (Codex/MCP + git)

This repo is commonly used with Codex + GitHub MCP, plus standard `git`/`gh` workflows.
To avoid interactive prompts (and to keep secrets out of the repo), use environment variables.

## Environment variables

- `GITHUB_MCP_PAT`: Personal Access Token used by the official GitHub MCP server (see `~/.codex/config.toml`).
- `GH_TOKEN`: Token used by GitHub CLI (`gh`) and tools built on top of it (including `gh-cli-mcp`).

Never commit tokens. Prefer storing them in your shell environment, a password manager/OS keychain,
or a local-only env file.

## Option A (recommended): `gh` CLI login + setup

This avoids putting a token in your git remote URL.

```bash
gh auth login
gh auth setup-git
```

## Option B: PAT via git credential helper (HTTPS)

If you already have a token, store it in the git credential helper so `git push` won’t block
waiting for a prompt.

```bash
git config --global credential.helper store
printf "protocol=https\nhost=github.com\nusername=x-access-token\npassword=$GH_TOKEN\n\n" | git credential approve
```

If you use `GITHUB_MCP_PAT` instead of `GH_TOKEN`, set `GH_TOKEN` to the same value in your shell:

```bash
export GH_TOKEN="$GITHUB_MCP_PAT"
```

## Making tokens available to Codex/MCP

The Codex GitHub MCP server configuration typically references the env var name:

```toml
[mcp_servers.github]
bearer_token_env_var = "GITHUB_MCP_PAT"
```

If Codex is not inheriting your shell environment, set `shell_environment_policy.inherit = "all"`
in `~/.codex/config.toml`.

