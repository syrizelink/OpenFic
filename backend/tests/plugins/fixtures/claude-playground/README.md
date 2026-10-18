# Official Claude Code playground Mod fixtures

Source: https://github.com/anthropics/claude-code-playground/tree/569c5283d9a0a7ee7938df85bb32e4f48cbb8c86/claude-code/mods

Commit: `569c5283d9a0a7ee7938df85bb32e4f48cbb8c86`.

All three Mods are version `0.1.0`, copyright Anthropic PBC, licensed Apache-2.0 (see LICENSE).
The original `.claude-plugin/plugin.json`, `hooks/hooks.json`, and executable `.mjs` files are copied byte for byte. `provenance.json` records their upstream SHA256 values. Documentation and screenshots are omitted from these offline runtime fixtures.

Backend integration tests install these fixtures as original Claude plugin archives. The browser test can instead install complete upstream folders by setting `OPENFIC_OFFICIAL_MODS_DIR=/path/to/claude-code-playground/claude-code/mods`; it checks the same hashes before installation. No OpenFic manifest or source-level patches are added to the upstream files.
