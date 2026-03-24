#!/usr/bin/env python3
"""
Project FINER — Unified Extraction CLI

Wraps the 15+ per-state extraction scripts into a single CLI with consistent
commands: list, run, import, validate, export, pipeline.

Usage:
    python3 db/extract.py list
    python3 db/extract.py run --state meghalaya
    python3 db/extract.py run --state meghalaya --dry-run
    python3 db/extract.py import --state meghalaya
    python3 db/extract.py validate --state meghalaya
    python3 db/extract.py export --state meghalaya
    python3 db/extract.py pipeline --state meghalaya
    python3 db/extract.py pipeline --state all
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent          # db/
PROJECT_DIR = SCRIPT_DIR.parent                        # projectfiner/
CONFIG_PATH = SCRIPT_DIR / "state_config.json"
SLBC_PUBLIC = PROJECT_DIR / "public" / "slbc-data"

# ── Colors ───────────────────────────────────────────────────────────────────

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_config():
    """Load state_config.json."""
    if not CONFIG_PATH.exists():
        print(f"{RED}Error: Config not found at {CONFIG_PATH}{RESET}")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_state_data_stats(slug):
    """Count quarters and find latest quarter for a state from its _complete.json."""
    complete_json = SLBC_PUBLIC / slug / f"{slug}_complete.json"
    if not complete_json.exists():
        return 0, None

    try:
        with open(complete_json) as f:
            data = json.load(f)
        quarters = data.get("quarters", {})
        if not quarters:
            return 0, None

        # Parse quarter keys to find latest
        def quarter_sort_key(qkey):
            """Sort quarter keys like 'june_2020', 'sept_2025'."""
            MONTH_MAP = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "sept": 9, "october": 10,
                "november": 11, "december": 12, "dec": 12,
            }
            parts = qkey.lower().replace("-", "_").split("_")
            if len(parts) >= 2:
                month_str = parts[0]
                year_str = parts[-1]
                month = MONTH_MAP.get(month_str, 0)
                try:
                    year = int(year_str)
                except ValueError:
                    year = 0
                return (year, month)
            return (0, 0)

        sorted_quarters = sorted(quarters.keys(), key=quarter_sort_key)
        latest_key = sorted_quarters[-1] if sorted_quarters else None

        # Get the human-readable period label from the latest quarter
        latest_label = None
        if latest_key and latest_key in quarters:
            latest_label = quarters[latest_key].get("period", latest_key)

        return len(quarters), latest_label
    except (json.JSONDecodeError, KeyError, TypeError):
        return 0, None


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_list(args):
    """List all states and their extraction status."""
    config = load_config()
    states = config["states"]

    print(f"\n{BOLD}Project FINER — State Extraction Status{RESET}")
    print(f"{'='*80}")
    print(f"{'State':<22} {'Quarters':>8}  {'Latest':<16} {'Script':>3}  {'Data Dir'}")
    print(f"{'-'*80}")

    total_quarters = 0
    states_with_scripts = 0
    states_with_data = 0

    for slug in sorted(states.keys()):
        info = states[slug]
        name = info["name"]
        has_script = info.get("extraction_script") is not None

        n_quarters, latest = get_state_data_stats(slug)
        total_quarters += n_quarters
        if has_script:
            states_with_scripts += 1
        if n_quarters > 0:
            states_with_data += 1

        script_marker = f"{GREEN}yes{RESET}" if has_script else f"{RED} no{RESET}"
        latest_str = latest or "-"
        if len(latest_str) > 16:
            latest_str = latest_str[:16]

        quarter_str = str(n_quarters) if n_quarters > 0 else f"{DIM}0{RESET}"
        data_dir = info.get("output_dir", "")
        # Shorten path for display
        data_dir_short = data_dir.replace(str(PROJECT_DIR), ".").replace("/Users/abhinav/Downloads/projectfiner", ".")

        print(f"  {name:<20} {quarter_str:>8}  {latest_str:<16} {script_marker}  {DIM}{data_dir_short}{RESET}")

    print(f"{'-'*80}")
    print(f"  {BOLD}{len(states)}{RESET} states | "
          f"{BOLD}{states_with_data}{RESET} with data | "
          f"{BOLD}{states_with_scripts}{RESET} with extraction scripts | "
          f"{BOLD}{total_quarters}{RESET} total quarters")
    print()


def cmd_run(args):
    """Run extraction for a specific state."""
    config = load_config()
    state_slug = normalize_state(args.state, config)
    if not state_slug:
        return

    info = config["states"][state_slug]

    if info.get("extraction_script") is None:
        print(f"{RED}No extraction script configured for {info['name']}{RESET}")
        print(f"  Source URL: {info.get('source_url', 'N/A')}")
        print(f"  Notes: {info.get('notes', '')}")
        return

    script = info["extraction_script"]
    script_dir = info["extraction_dir"]
    script_path = os.path.join(script_dir, script)

    if not os.path.exists(script_path):
        print(f"{RED}Extraction script not found: {script_path}{RESET}")
        return

    # Build command
    cmd = [sys.executable, script_path] + info.get("extraction_args", [])

    # For jharkhand/odisha/chhattisgarh, add --output-dir if needed
    if state_slug in ("jharkhand", "odisha") and info.get("output_dir"):
        cmd.extend(["--output-dir", info["output_dir"]])

    print(f"\n{BOLD}Extract: {info['name']}{RESET}")
    print(f"  Script:  {script_path}")
    print(f"  Args:    {' '.join(info.get('extraction_args', [])) or '(none)'}")
    print(f"  CWD:     {script_dir}")
    print(f"  Output:  {info.get('output_dir', 'N/A')}")
    print(f"  Command: {' '.join(cmd)}")
    print()

    if args.dry_run:
        print(f"{YELLOW}[DRY RUN] Would execute the command above.{RESET}")
        return

    print(f"{CYAN}Running extraction...{RESET}")
    result = subprocess.run(cmd, cwd=script_dir)

    if result.returncode == 0:
        print(f"\n{GREEN}Extraction completed successfully.{RESET}")
    else:
        print(f"\n{RED}Extraction failed (exit code {result.returncode}).{RESET}")
        return result.returncode


def cmd_standardize(args):
    """Run field standardization for a state."""
    config = load_config()
    state_slug = normalize_state(args.state, config)
    if not state_slug:
        return

    info = config["states"][state_slug]
    std_script = config.get("standardize_script")

    if not std_script or not os.path.exists(std_script):
        print(f"{YELLOW}Standardize script not found: {std_script}{RESET}")
        print(f"  Skipping standardization step.")
        return

    cmd = [sys.executable, std_script]
    cwd = os.path.dirname(std_script)

    print(f"\n{BOLD}Standardize: {info['name']}{RESET}")
    print(f"  Script: {std_script}")
    print(f"  Command: {' '.join(cmd)}")
    print()

    if args.dry_run:
        print(f"{YELLOW}[DRY RUN] Would execute the command above.{RESET}")
        return

    print(f"{CYAN}Running standardization...{RESET}")
    result = subprocess.run(cmd, cwd=cwd)

    if result.returncode == 0:
        print(f"\n{GREEN}Standardization completed successfully.{RESET}")
    else:
        print(f"\n{RED}Standardization failed (exit code {result.returncode}).{RESET}")
        return result.returncode


def cmd_import(args):
    """Import SLBC data into SQLite for a state (or all)."""
    config = load_config()
    import_script = config.get("import_script")

    if not import_script or not os.path.exists(import_script):
        print(f"{RED}Import script not found: {import_script}{RESET}")
        return

    state_slug = normalize_state(args.state, config)
    if not state_slug:
        return

    info = config["states"][state_slug]

    # import_slbc.py imports all states at once — no per-state filtering.
    # We still run it but tell the user.
    cmd = [sys.executable, import_script]
    cwd = os.path.dirname(import_script)

    print(f"\n{BOLD}Import: {info['name']}{RESET}")
    print(f"  Script: {import_script}")
    print(f"  Note:   import_slbc.py imports ALL 22 states; filtering to one state")
    print(f"          is not supported. The full import takes ~30s.")
    print(f"  Command: {' '.join(cmd)}")
    print()

    if args.dry_run:
        print(f"{YELLOW}[DRY RUN] Would execute the command above.{RESET}")
        return

    print(f"{CYAN}Running import...{RESET}")
    result = subprocess.run(cmd, cwd=cwd)

    if result.returncode == 0:
        print(f"\n{GREEN}Import completed successfully.{RESET}")
    else:
        print(f"\n{RED}Import failed (exit code {result.returncode}).{RESET}")
        return result.returncode


def cmd_validate(args):
    """Run data validation for a state."""
    config = load_config()
    validate_script = config.get("validate_script")

    if not validate_script or not os.path.exists(validate_script):
        print(f"{RED}Validate script not found: {validate_script}{RESET}")
        return

    state_slug = normalize_state(args.state, config)
    if not state_slug:
        return

    info = config["states"][state_slug]

    cmd = [sys.executable, validate_script, "--state", state_slug]
    cwd = str(PROJECT_DIR)

    print(f"\n{BOLD}Validate: {info['name']}{RESET}")
    print(f"  Script: {validate_script}")
    print(f"  Command: {' '.join(cmd)}")
    print()

    if args.dry_run:
        print(f"{YELLOW}[DRY RUN] Would execute the command above.{RESET}")
        return

    print(f"{CYAN}Running validation...{RESET}")
    result = subprocess.run(cmd, cwd=cwd)

    if result.returncode == 0:
        print(f"\n{GREEN}Validation completed successfully.{RESET}")
    else:
        print(f"\n{RED}Validation failed (exit code {result.returncode}).{RESET}")
        return result.returncode


def cmd_export(args):
    """Export timeseries JSON from SQLite."""
    config = load_config()
    export_script = config.get("export_script")

    if not export_script or not os.path.exists(export_script):
        print(f"{RED}Export script not found: {export_script}{RESET}")
        return

    state_slug = normalize_state(args.state, config)
    if not state_slug:
        return

    info = config["states"][state_slug]

    # export_timeseries.py exports all states
    cmd = [sys.executable, export_script]
    cwd = os.path.dirname(export_script)

    print(f"\n{BOLD}Export: {info['name']}{RESET}")
    print(f"  Script: {export_script}")
    print(f"  Note:   export_timeseries.py exports ALL states from SQLite.")
    print(f"  Command: {' '.join(cmd)}")
    print()

    if args.dry_run:
        print(f"{YELLOW}[DRY RUN] Would execute the command above.{RESET}")
        return

    print(f"{CYAN}Running export...{RESET}")
    result = subprocess.run(cmd, cwd=cwd)

    if result.returncode == 0:
        print(f"\n{GREEN}Export completed successfully.{RESET}")
    else:
        print(f"\n{RED}Export failed (exit code {result.returncode}).{RESET}")
        return result.returncode


def cmd_pipeline(args):
    """Run full pipeline: extract -> standardize -> import -> validate -> export."""
    config = load_config()

    if args.state and args.state.lower() == "all":
        # Run pipeline for all states with extraction scripts
        states_to_run = [
            slug for slug, info in config["states"].items()
            if info.get("extraction_script") is not None
        ]
        print(f"\n{BOLD}Pipeline: ALL {len(states_to_run)} states with extraction scripts{RESET}")
        print(f"  States: {', '.join(sorted(states_to_run))}")
        print()

        if args.dry_run:
            print(f"{YELLOW}[DRY RUN] Would run pipeline for each state above.{RESET}")
            return

        # Run extraction for each state
        failed = []
        for slug in sorted(states_to_run):
            print(f"\n{'='*60}")
            print(f"{BOLD}  Pipeline step: Extract {config['states'][slug]['name']}{RESET}")
            print(f"{'='*60}")
            args_copy = argparse.Namespace(state=slug, dry_run=False)
            rc = cmd_run(args_copy)
            if rc:
                failed.append(slug)
                print(f"{YELLOW}Continuing with next state...{RESET}")

        # Standardize (runs on all states at once)
        print(f"\n{'='*60}")
        print(f"{BOLD}  Pipeline step: Standardize all states{RESET}")
        print(f"{'='*60}")
        args_std = argparse.Namespace(state=list(config["states"].keys())[0], dry_run=False)
        cmd_standardize(args_std)

        # Import all
        print(f"\n{'='*60}")
        print(f"{BOLD}  Pipeline step: Import all into SQLite{RESET}")
        print(f"{'='*60}")
        args_imp = argparse.Namespace(state=list(config["states"].keys())[0], dry_run=False)
        cmd_import(args_imp)

        # Validate each
        for slug in sorted(states_to_run):
            if slug not in failed:
                print(f"\n{'='*60}")
                print(f"{BOLD}  Pipeline step: Validate {config['states'][slug]['name']}{RESET}")
                print(f"{'='*60}")
                args_val = argparse.Namespace(state=slug, dry_run=False)
                cmd_validate(args_val)

        # Export
        print(f"\n{'='*60}")
        print(f"{BOLD}  Pipeline step: Export timeseries JSON{RESET}")
        print(f"{'='*60}")
        args_exp = argparse.Namespace(state=list(config["states"].keys())[0], dry_run=False)
        cmd_export(args_exp)

        # Summary
        print(f"\n{'='*60}")
        print(f"{BOLD}Pipeline Summary{RESET}")
        print(f"  Succeeded: {len(states_to_run) - len(failed)}")
        if failed:
            print(f"  {RED}Failed: {', '.join(failed)}{RESET}")
        print()
        return

    # Single state pipeline
    state_slug = normalize_state(args.state, config)
    if not state_slug:
        return

    info = config["states"][state_slug]
    steps = [
        ("Extract", cmd_run),
        ("Standardize", cmd_standardize),
        ("Import", cmd_import),
        ("Validate", cmd_validate),
        ("Export", cmd_export),
    ]

    print(f"\n{BOLD}Pipeline: {info['name']}{RESET}")
    print(f"  Steps: Extract -> Standardize -> Import -> Validate -> Export")
    print()

    if args.dry_run:
        for step_name, step_fn in steps:
            print(f"\n{BOLD}--- Step: {step_name} ---{RESET}")
            step_args = argparse.Namespace(state=state_slug, dry_run=True)
            step_fn(step_args)
        return

    for i, (step_name, step_fn) in enumerate(steps, 1):
        print(f"\n{'='*60}")
        print(f"{BOLD}  Step {i}/5: {step_name} — {info['name']}{RESET}")
        print(f"{'='*60}")

        step_args = argparse.Namespace(state=state_slug, dry_run=False)
        rc = step_fn(step_args)
        if rc:
            print(f"\n{RED}Pipeline stopped at step '{step_name}' due to error.{RESET}")
            return rc

    print(f"\n{GREEN}Pipeline completed successfully for {info['name']}.{RESET}")


# ── Helpers ──────────────────────────────────────────────────────────────────

def normalize_state(state_input, config):
    """Resolve user input to a state slug. Returns slug or None."""
    if not state_input:
        print(f"{RED}Error: --state is required.{RESET}")
        return None

    slug = state_input.lower().strip().replace(" ", "-")
    states = config["states"]

    # Direct match
    if slug in states:
        return slug

    # Try matching by name (case-insensitive)
    for key, info in states.items():
        if info["name"].lower() == slug.replace("-", " "):
            return key

    # Try partial match
    matches = [k for k in states if slug in k or slug in states[k]["name"].lower()]
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"{RED}Ambiguous state '{state_input}'. Matches: {', '.join(matches)}{RESET}")
        return None

    print(f"{RED}Unknown state: '{state_input}'{RESET}")
    print(f"  Available states: {', '.join(sorted(states.keys()))}")
    return None


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="extract.py",
        description="Project FINER — Unified extraction CLI for SLBC state data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 db/extract.py list
  python3 db/extract.py run --state meghalaya
  python3 db/extract.py run --state meghalaya --dry-run
  python3 db/extract.py import --state bihar
  python3 db/extract.py validate --state assam
  python3 db/extract.py export --state west-bengal
  python3 db/extract.py pipeline --state meghalaya
  python3 db/extract.py pipeline --state all
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # list
    sp_list = subparsers.add_parser("list", help="List all states and their extraction status")
    sp_list.set_defaults(func=cmd_list)

    # run
    sp_run = subparsers.add_parser("run", help="Run extraction for a state")
    sp_run.add_argument("--state", required=True, help="State slug (e.g., meghalaya, west-bengal)")
    sp_run.add_argument("--dry-run", action="store_true", help="Show what would be done without doing it")
    sp_run.set_defaults(func=cmd_run)

    # standardize
    sp_std = subparsers.add_parser("standardize", help="Run field standardization")
    sp_std.add_argument("--state", required=True, help="State slug")
    sp_std.add_argument("--dry-run", action="store_true", help="Show what would be done")
    sp_std.set_defaults(func=cmd_standardize)

    # import
    sp_import = subparsers.add_parser("import", help="Import extracted data into SQLite")
    sp_import.add_argument("--state", required=True, help="State slug")
    sp_import.add_argument("--dry-run", action="store_true", help="Show what would be done")
    sp_import.set_defaults(func=cmd_import)

    # validate
    sp_validate = subparsers.add_parser("validate", help="Validate data quality for a state")
    sp_validate.add_argument("--state", required=True, help="State slug")
    sp_validate.add_argument("--dry-run", action="store_true", help="Show what would be done")
    sp_validate.set_defaults(func=cmd_validate)

    # export
    sp_export = subparsers.add_parser("export", help="Export timeseries JSON from SQLite")
    sp_export.add_argument("--state", required=True, help="State slug")
    sp_export.add_argument("--dry-run", action="store_true", help="Show what would be done")
    sp_export.set_defaults(func=cmd_export)

    # pipeline
    sp_pipeline = subparsers.add_parser("pipeline", help="Run full pipeline: extract -> standardize -> import -> validate -> export")
    sp_pipeline.add_argument("--state", required=True, help="State slug, or 'all' for all states")
    sp_pipeline.add_argument("--dry-run", action="store_true", help="Show what would be done")
    sp_pipeline.set_defaults(func=cmd_pipeline)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
