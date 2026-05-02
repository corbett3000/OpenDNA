# OpenDNA macOS shell

Native SwiftUI shell around the existing local Python engine.

What it does:

- discovers this repo checkout
- launches `opendna serve` from `.venv`
- embeds the existing local web UI inside `WKWebView`
- adds native macOS commands for picking a DNA file, restarting the engine, and opening the UI in a browser

What it does not do yet:

- bundle Python or the OpenDNA engine into a standalone distributable app
- replace the current HTML report with native SwiftUI views
- ingest biomarker files directly

Build it from the repo root:

```bash
./scripts/build_macos_shell.sh --open
```

The generated app bundle lands at `build/macos/OpenDNA.app`.

