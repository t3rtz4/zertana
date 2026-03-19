# Contributing to Zertana

First off, thank you for considering contributing. Zertana is a community tool
built for the security learning community, and every contribution matters.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute ?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Submitting a Pull Request](#submitting-a-pull-request)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)
- [Style Guide](#style-guide)

---

## Code of Conduct

Be respectful. This project is about learning and building tools for ethical
security research. Contributions that facilitate illegal activity will not be
accepted.

---

## How Can I Contribute ?

There are many ways to help beyond writing code:

- **Report bugs** — open an issue with a clear reproduction case
- **Test on different distros** — Zertana is primarily tested on Fedora;
  reports from Ubuntu, Arch, and others are very welcome
- **Improve documentation** — fix typos, clarify steps, add examples
- **Add VulnHub machine compatibility notes** — some machines behave oddly
  under KVM; document known quirks
- **Implement roadmap features** — see the roadmap in the README

---

## Development Setup

### Prerequisites

- Fedora, Ubuntu, Debian, or Arch Linux
- KVM/libvirt stack installed and working
- Python 3.11+
- `qemu-img`, `7z` available in PATH

### Clone and install in editable mode

```bash
git clone https://github.com/t3rtz4/zertana.git
cd zertana
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Verify your environment

```bash
zertana --help
```

If the preflight checks pass, you're good to go.

---

## Project Structure

```
zertana/
├── cli.py          # Entry point, argument parsing, scenario orchestration
├── checks.py       # Preflight: RAM, disk, QEMU tools, KVM connectivity
├── wizard.py       # Interactive InquirerPy configuration prompts
├── disk.py         # Image download, extraction, conversion, linked clones
└── hypervisor.py   # libvirt network and VM define/start/teardown
```

Each file has a single, clear responsibility. Keep it that way, and if a new
feature needs a significant amount of logic, create a new module rather than
bloating an existing one.

---

## Submitting a Pull Request

1. **Fork** the repository and create a branch from `master`:
   ```bash
   git checkout -b feat/feature-name
   ```

2. **Make your changes** — keep commits focused and atomic. One logical change
   per commit.

3. **Test manually** — Zertana doesn't have automated tests yet (contributions
   welcome). At minimum, run through the affected scenario end to end:
   - Target only
   - Attack box only
   - Full lab

4. **Write a clear commit message**:
   ```
   feat: add Metasploitable as a static target

   - Added static_targets.json with Metasploitable 2 entry
   - wizard.py now merges static targets with owleye DB before display
   - disk.py handles direct VMDK download for static targets
   ```

5. **Open a Pull Request** against `master` with:
   - A description of what the PR does and why
   - Steps to test it
   - Any known limitations or follow up work

---

## Reporting Bugs

Please open a GitHub Issue and include:

- **Your distro and version** (e.g. Fedora 41)
- **Python version** (`python --version`)
- **Full error output** — paste the complete traceback
- **Steps to reproduce** — be specific about which scenario you were running
- **VulnHub machine name** if the bug is target specific

---

## Suggesting Features

Open a GitHub Issue with the `enhancement` label. Describe:

- The problem you're trying to solve
- Your proposed solution
- Any alternatives you considered

Check the roadmap in the README first, it may already be planned.

---

## Style Guide

Zertana follows these conventions:

**Python:**
- Type hints on all function signatures
- Private helpers prefixed with `_`
- `Rich` for all console output — no bare `print()`
- Subprocess calls always use `check=True` and `timeout`
- Secrets and credentials never hardcoded beyond the known Kali defaults

**Naming:**
- Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Files: `snake_case.py`

**Console output style:**
- `[cyan]` — in-progress actions
- `[green]` — success
- `[yellow]` — warnings / non-fatal notices
- `[red]` — errors / failures
- `[dim]` — cleanup / verbose detail

Keeping the output consistent makes the UX feel cohesive across all modules.

---

## A Note on Scope

Zertana is a **local KVM lab builder**. Contributions should stay within that
scope. It is not a network scanner, exploit framework, or general purpose VM
manager. When in doubt, open an issue and discuss before investing time in a
large PR.
