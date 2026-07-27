---
name: fnm Node on Replit PATH
description: How to keep node/npx visible to Replit GUI features when using fnm instead of the Replit Node module
---

# fnm-managed Node and the Replit default PATH

Rule: when the Replit Node module is removed in favor of fnm, GUI features (e.g. Skills tab "Install") spawn `npx` with the bare workspace PATH — no shell init, no `~/.profile`. Symlinks must live in a folder already on that default PATH.

**Why:** removing the Node module also removes `~/workspace/.config/npm/node_global/bin` from the default PATH, so links placed there stop working ("spawn npx ENOENT"). `.replit` cannot be edited directly, and overriding PATH via env vars is risky.

**How to apply:** symlink `node/npm/npx/pnpm/pnpx` from `$FNM_DIR/aliases/default/bin` into `~/workspace/.pythonlibs/bin` (the only writable dir on the default PATH). Verify with `env -i PATH=... npx --version`. Re-create links if a Python reinstall clears that folder.

Related gotchas:
- `~/.bashrc` is read-only; `~/.profile` is writable for `fnm env` shell init.
- Editing a Makefile with the edit tool can silently convert recipe tabs to spaces — re-check with `cat -A` and restore tabs if make reports "missing separator".
