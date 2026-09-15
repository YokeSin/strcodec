# strcodec — SPSS Modeler `.str` ⇄ Jython codec for coding agents

English | [日本語](README.md)

strcodec is a toolkit that converts IBM SPSS Modeler stream files (`.str`, a binary format) into **normalized Jython plus a summary** that coding agents can read. It also generates a **self-contained script that can reproduce the original stream** from that Jython. The toolkit includes skills and hooks for IBM Bob IDE, while its CLI can also be used with any agent or manually. It provides two main capabilities:

- **decode**: Converts `.str` into `<name>.strcode/`, containing `summary.md`, an editable `stream.py`, `structure.json`, and model nugget `.nod` files. Agents can read these artifacts to explain a stream.
- **rebuild**: Converts `stream.py` into Jython that can run in Modeler and produce `<name>_rebuilt.str`. Edit `stream.py` and rebuild it to modify or recreate a stream without overwriting the original. Use `report` and `verify` to inspect the result.

For details on how it works, artifact specifications, the rationale behind conversion rules, and validation records, see the [strcodec manual](docs/strcodec-manual.md) (Japanese).

---

## Requirements

| Component        | Requirement                                      | Notes                                                                                                                                                                                                                      |
| ---------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OS               | Windows 10/11                                    | The launcher is a Windows`cmd` script. Other operating systems have not been tested.                                                                                                                                     |
| IBM SPSS Modeler | Client 18.5 or later (`clemb.exe` and license) | Version 19.0 has been tested on an actual installation. Versions 18.5 through 18.x are expected to work.                                                                                                                   |
| Python           | CPython 3.10 or later                            | Falls back to the CPython bundled with Modeler if no other compatible installation is available.                                                                                                                           |
| IBM Bob IDE      | Optional                                         | Required only for the skills and hooks. Not needed for CLI-only use.                                                                                                                                                       |
| MCP servers      | Optional (recommended)                           | [spss-clemb-mcp](https://github.com/hkwd/spss-clemb-mcp) lets agents run Jython; [ibm-docs-mcp](https://github.com/hkwd/ibm-docs-mcp/blob/main/README_EN.md) lets them verify node specifications against IBM documentation. |

Two Python runtimes are involved. The CPython listed above handles local operations such as the CLI, hooks, and conversion. Jython used to extract and rebuild `.str` files runs inside Modeler's Jython 2.7 environment through `clemb.exe`. See section 3.2 of the manual for details.

## Installation

### Option A: Use the installation script (recommended)

Open PowerShell at the root of the workspace where you work with stream files, then run:

```powershell
irm https://raw.githubusercontent.com/YokeSin/strcodec/main/install-strcodec.ps1 | iex
```

If you have already cloned this repository, you can install from that clone:

```powershell
.\install-strcodec.ps1 -Workspace <your-workspace>
```

The script performs the following steps. Running it again updates the installation.

1. Copies `.bob/strcodec/` and `.bob/skills/{spss-str-decode,spss-str-rebuild,_shared}` into the workspace, preserving existing user settings in `python.path`, `logs/`, and `config.json`.
2. Merges three hooks into `.bob/settings.json`, preserving existing hooks and creating `settings.json.bak-<timestamp>` before making changes.
3. Creates `AGENTS.md`, or appends the strcodec section once if the file already exists.
4. Adds generated-artifact exclusion patterns to `.gitignore` when the workspace is a Git repository.
5. Checks whether spss-clemb-mcp and ibm-docs-mcp are registered with Bob. If either is missing, it displays the corresponding repository URL. The MCP servers themselves must be installed separately.
6. Runs `strcodec.cmd python-info` and `status` to verify the installation.

Because arguments cannot be passed through `irm | iex`, set the `STRCODEC_WORKSPACE` environment variable beforehand to target a different workspace. When running the script from a file, you can use `-Workspace`, `-Source <clone>`, `-NoHooks`, and `-NoAgentsMd`.

### Option B: Install manually

1. **Copy the files**: Copy `.bob/` and `AGENTS.md` from this repository to the root of the workspace where you work with streams. If the workspace already has a `.bob/` directory, add `strcodec/` and `skills/`, then merge the `hooks` from `settings.json`.

   ```text
   <your-workspace>/
   ├── AGENTS.md
   ├── .bob/
   │   ├── settings.json          <- hook definitions (launched through strcodec.cmd)
   │   ├── strcodec/              <- toolkit (strcodec.cmd is the launcher)
   │   └── skills/spss-str-decode/, spss-str-rebuild/, _shared/
   └── (your *.str files)
   ```
2. **Check Python**: Run `.\.bob\strcodec\strcodec.cmd python-info` to see which `python.exe` is selected. Candidates are resolved in this order: `STRCODEC_PYTHON` -> `.bob\strcodec\python.path` -> `py -3` -> `python` on `PATH` -> the version bundled with Modeler as a fallback. To use a specific Python installation, configure `STRCODEC_PYTHON` or `python.path` (manual section 3.2).
3. **Locate clemb.exe**: No configuration is needed if it is installed in the default location, `C:\Program Files\IBM\SPSS\Modeler\<version>\bin\clemb.exe`. Otherwise, set `"clemb_path"` in `.bob/strcodec/config.json` or the `SPSS_MODELER_CLEMB_PATH` environment variable. strcodec also checks the spss-clemb-mcp configuration file automatically.
4. **Install MCP servers (optional, recommended)**: To let agents run rebuild scripts or look up node specifications, install the following two servers and register them in `.bob/mcp.json`. See each repository for installation instructions and configuration examples.

   - https://github.com/hkwd/spss-clemb-mcp
   - https://github.com/hkwd/ibm-docs-mcp
5. **Configure Bob IDE**: Hooks are enabled simply by placing `.bob/settings.json` in the workspace. By default, Bob asks for approval before running skills. To skip the prompt each time, enable Skills under Bob's **Auto-approving actions** setting.
6. **Verify the installation**:

   ```powershell
   cd <your-workspace>
   .\.bob\strcodec\strcodec.cmd status                       # Active Python/clemb, .str files, and cache status
   .\.bob\strcodec\strcodec.cmd decode path\to\stream.str    # Prints a summary; ~20 seconds initially, then immediate from cache
   ```

## Usage

To try strcodec, use the included sample: a stream with synthetic data and a C5.0 nugget, consisting of eight nodes and seven links. See [samples/README.md](samples/README.md) (Japanese) for details.

```powershell
.\.bob\strcodec\strcodec.cmd decode samples\campaign_response.str
```

### In Bob IDE

| Goal                                     | Example prompt                                                                    |
| ---------------------------------------- | --------------------------------------------------------------------------------- |
| Ask for an explanation of a stream       | "Explain`@~.str`."                                                              |
| Modify and recreate a stream             | "In`~.str`, change the expression ... to ..., then recreate the `.str` file." |
| Rebuild a stream whose data paths differ | "Rebuild`x.str` with `--map \"C:/old/dir=C:/new/dir\"`."                      |
| Retrain a model                          | "Rebuild`x.str` with `--retrain`." Data access is required.                   |

When a prompt mentions a `.str` file, a hook automatically decodes it and injects the summary into the context. At the start of a session, another hook lists `.str` files in the workspace and decodes any uncached files in the background. If an agent attempts to read a `.str` file with `read_file`, a guard hook blocks the operation and suggests the correct procedure.

An unedited transcript of a real workflow, from explaining the sample through adding a Select node and rebuilding it to running `report` and `verify`, is available in [samples/example-session.md](samples/example-session.md) (Japanese).

An agent typically follows these steps, as defined in the `spss-str-decode` and `spss-str-rebuild` skills:

1. Run `decode` and read `summary.md`, unless the hook has already injected it.
2. Read only the relevant node blocks in `stream.py`. Each block starts with a `# ---- <var> | <type> | ...` heading.
3. To make changes, edit `stream.py` while preserving one statement per line, `u"..."` strings, `None`, and `NUGGET(...)` markers.
4. Run `rebuild` to generate the script, then execute it with `execute_clemb` from spss-clemb-mcp.
5. Run `report` and `verify`, then report the resulting `.str` path and verification results.

### CLI

```text
.bob\strcodec\strcodec.cmd <command> ...        (If Python is available, python .bob/strcodec/strcodec.py <command> also works.)

decode      <file.str> [--force] [--quiet] [--json] [--max-lines N]
            Decode a .str file into <stem>.strcode/ and print summary.md. Returns immediately when cached.
rebuild     <file.str | dir.strcode> [--out X.str] [--retrain] [--map OLD=NEW]... [--no-validate] [--run]
            [--coding-header] [--allow-stale] [--allow-issues]
            Generate rebuild/<stem>_rebuild.py from stream.py. With --run, also run clemb and print a report.
            Refuses to generate if the source .str changed, the tool version differs, or a .nod file is missing.
            Use --allow-stale to continue despite those conditions.
            With --run, exits with 0 for STATUS OK or OK WITH WARNINGS. With --allow-issues, it also exits with 0
            when the stream was saved despite issues.
            --coding-header is for the Modeler GUI and cannot be combined with --run.
report      <file.str | dir.strcode> [--allow-issues]
            Generate a report from the most recent rebuild result, rebuild/<stem>_rebuild_result.json.
            Exit-code rules are the same as for --run.
verify      <a.str> <b.str> [--force] [--strict]
            Compare two streams. Exits with 0 and STRUCTURE_MATCH when their structure (types, labels,
            coordinates, and links) matches. Lists differences in node property values and stream settings.
            With --strict, exits with 1 if any such differences exist.
prewarm     [--background] [--max N] [--root DIR]
            Decode all uncached .str files in the workspace.
status      [--root DIR]
            Show the active Python and clemb executables, available .str files, and cache status.
python-info / --which
            Show the python.exe selected by the launcher and all candidates.
hook        <prompt | session-start | guard-read>
            Entry point for Bob hooks. Reads JSON from stdin.
```

There are three ways to run a reproduction script:

| Method                 | Usage                                                                                                                                                                                                          |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Agent (spss-clemb-mcp) | `execute_clemb(script_file=".../rebuild/<stem>_rebuild.py", working_directory=".../<stem>.strcode", log_file=".../rebuild/<stem>_rebuild.log")` — the `rebuild` output displays these arguments verbatim. |
| CLI                    | `strcodec.cmd rebuild <file.str> --run`                                                                                                                                                                      |
| Modeler GUI            | Open`<stem>_rebuild.py` under **Tools > Standalone Script** and run it. Generate it with `--coding-header` to handle Japanese text safely.                                                           |

## How It Works

```text
file.str --(extract with JythonGenerator through clemb)--> generated_raw.py + structure.json + nuggets/*.nod
         --(normalize)-----------------------------------> stream.py       <- canonical source agents read and edit
         --(summarize)-----------------------------------> summary.md      <- injected into context by the hook

stream.py --(generate reproduction script)--> rebuild/<stem>_rebuild.py
          --(run through clemb / MCP / GUI)---> <stem>_rebuilt.str + result JSON --> report / verify
```

strcodec invokes `JythonGenerator`, the backend for Modeler's **Paste Node as Script** GUI feature, from within `clemb.exe` to obtain Jython that reconstructs the stream. Because the generated output cannot run as-is, a thin post-processing layer makes it executable.

| Issue in generated output                                                           | How strcodec handles it                                                                                               |
| ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `null` in list elements is not valid Python `None`                              | Normalizes it to`None` at the token level without changing string contents.                                         |
| The complete script exceeds the JVM's 64 KB method limit                            | Splits it into functions of 40 statements each and loads large literals through JSON.                                 |
| Model nuggets created with`createAt` are empty and cause `NullPointerException` | Saves them as`.nod` files and transfers each trained model without retraining. `--retrain` can rerun the builder. |
| Nugget internal IDs are specific to the source stream                               | Does not restore them, allowing Modeler to assign new IDs.                                                            |
| Data paths differ between environments                                              | Checks for path existence and supports prefix replacement through`--map OLD=NEW`.                                   |
| Some setters raise exceptions                                                       | Records failures and continues, reporting known harmless cases separately.                                            |

See sections 2 through 11 of the manual for extraction templates, normalization rules, the rebuild script and runtime, hooks and skills, artifact formats, configuration options, and validation evidence for the conversion rules.

## Generated Artifacts

strcodec creates `<stem>.strcode/` next to the `.str` file. It contains `summary.md` (summary), `stream.py` (editable Jython), `structure.json` (machine-readable structure), model files such as `nuggets/*.nod`, `rebuild/` (reproduction scripts, logs, result JSON, and reports), and `meta.json` (cache key). By default, a rebuilt stream is written to `<stem>_rebuilt.str`. See section 8 of the manual for each file's specification.

The `.strcode/` directory contains derived artifacts and can be regenerated. The included `.gitignore` excludes `*.strcode/`, `*_rebuilt.str`, logs, personal settings, and, by default, `*.str` and `*.nod` because they may contain business data. Explicitly add any files you intend to share.

## Repository Layout

```text
.
├── README.md
├── README.en.md                   English README
├── install-strcodec.ps1           Installation/update script (Option A)
├── AGENTS.md                      Persistent instructions for agents
├── docs/strcodec-manual.md        Detailed manual
├── samples/                       Test sample: synthetic data and a stream containing a C5.0 nugget
└── .bob/
    ├── settings.json              Hooks launched through strcodec.cmd hook ...
    ├── skills/                    spss-str-decode, spss-str-rebuild, _shared/strcodec-reference.md
    └── strcodec/                  Toolkit: CPython 3.10+, standard library only
        ├── strcodec.cmd           Windows launcher
        ├── strcodec.py            CLI
        ├── jython/                Extraction template and rebuild runtime run by clemb under Jython 2.7
        ├── hooks/                 Three Bob hooks
        └── tests/                 Unit tests: python -m unittest discover -s .bob/strcodec/tests
```

See section 3 of the manual for the role of each module and section 11 for configuration options in `.bob/strcodec/config.json`.

## Limitations and Handling Notes

- Features and behavior may vary by Modeler version. Version 19.0 has been tested.
- The launcher is Windows-only. On other operating systems, run `python .bob/strcodec/strcodec.py` directly. This has not been tested.
- SuperNodes are transferred whole as `.nod` files; editing their contents is not supported. Extension nodes and other nodes Modeler identifies as `unknown*` can likewise be reproduced only through `.nod` transfer.
- The first decode takes 15 to 25 seconds, including clemb startup. Subsequent decodes use the cache. Because decoding runs synchronously when a prompt is submitted, the user waits during the initial run.
- `.strcode/` can contain field names, value ranges, data paths, CLEM expressions, and `.nod` files with trained models. Review its contents before sharing or committing artifacts from streams that handle sensitive data.
- Hooks and tools launch `clemb.exe` with the current user's permissions. Opening a `.str` file is read-only, but the `rebuild` validation step and `--retrain` read from data sources. Use `--no-validate` to skip validation.

See section 14 of the manual for all known issues and possible extensions.

## Troubleshooting

| Symptom                                                | What to check                                                                                                                                                                                 |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `No usable CPython 3.10+ was found`                  | Install CPython 3.10 or later (the installation used by spss-clemb-mcp is fine), or inspect candidates with`strcodec.cmd python-info` and configure `STRCODEC_PYTHON` or `python.path`. |
| A hook does not inject anything                        | Check`.bob/strcodec/logs/hooks.log`. Run `strcodec.cmd status` manually to confirm the launcher starts.                                                                                   |
| `decode failed: clemb extraction failed`             | Check the end of`<stem>.strcode/_extract.log` for license errors, path problems, or a corrupt `.str` file.                                                                                |
| The report says`path not found` or validation failed | The data is unavailable in the current environment. Replace its path with`--map OLD=NEW`. The `.str` itself has still been saved.                                                         |

See section 13 of the manual for other symptoms.

## License

[MIT License](LICENSE). The code in this repository, including the CPython tools, Jython templates, launcher, installation script, skills, hooks, and documentation, uses only the standard library and contains no third-party code.

IBM SPSS Modeler itself, its sample streams and sample data in the `Demos` directory, its bundled Python, and its documentation are the property of IBM and are not included in this repository. The `.gitignore` excludes `*.str` and `*.nod`. The streams and data under `samples/`, as well as `tests/fixtures/`, are entirely fictional synthetic data, created by loading randomly generated CSV files into SPSS Modeler 19.0.

## Disclaimer and Trademarks

- This is an independent personal project, is not affiliated with IBM, and is not supported by IBM.
- It may stop working with future Modeler releases. Use it at your own risk.
- IBM, SPSS, IBM SPSS Modeler, and IBM Bob are trademarks or registered trademarks of IBM Corporation.

## Acknowledgments

- [hkwd/spss-clemb-mcp](https://github.com/hkwd/spss-clemb-mcp) — provides a mechanism for running `clemb.exe` through MCP and served as a reference for invoking clemb.
- [hkwd/ibm-docs-mcp](https://github.com/hkwd/ibm-docs-mcp) — provides search access to IBM documentation.
