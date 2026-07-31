# Support

Open an issue at:

https://github.com/zhanghao1903/macos-computer-use/issues

Include:

- plugin, Codex, and Claude Code versions;
- operating system and Python version;
- sanitized `workflowctl.py status` and `claudectl.py status` output;
- lifecycle stage, bridge request kind, and error `kind`;
- whether the marketplace is Git or local;
- whether the dispatch is `RUNNING`, `UNKNOWN`, or `COMPLETED`;
- minimal reproduction steps.

Do not include tokens, cookies, authorization headers, credential paths,
private source, raw prompts/transcripts, diffs, package credentials, signed
URLs, or unredacted logs.

For `UNKNOWN`, preserve the exact request, repository worktree, result file,
and local project state before further action. Recover only that message with
the recorded session. For corrupt state, preserve the exact project directory.
For failed publication, do not submit a different target or digest under the
old authorization.
