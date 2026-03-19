# Zertana 🦉

[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)](https://kernel.org/)
[![owleye](https://img.shields.io/badge/companion-owleye-blueviolet)](https://github.com/t3rtz4/owleye)

> Your personal CTF lab builder — powered by KVM/QEMU

Zertana is a CLI tool that spins up **isolated penetration testing labs** on your local machine using KVM/libvirt. Pick a VulnHub target, optionally deploy a Kali attack box, and get hacking — all on a private sandboxed network, in minutes.

```
███████╗███████╗██████╗ ████████╗█████╗ ███╗   ██╗█████╗
╚══███╔╝██╔════╝██╔══██╗╚══██╔══╝██╔══██╗████╗  ██║██╔══██╗
  ███╔╝ █████╗  ██████╔╝   ██║   ███████║██╔██╗ ██║███████║
 ███╔╝  ██╔══╝  ██╔══██╗   ██║   ██╔══██║██║╚██╗██║██╔══██║
███████╗███████╗██║  ██║   ██║   ██║  ██║██║ ╚████║██║  ██║
╚══════╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝
                Your personal CTF lab builder
```

---

## Features

- **One command lab setup** — attacker + target, isolated network, ready to hack
- **VulnHub integration** — browse and deploy any VulnHub machine via fuzzy search
- **Official Kali QEMU image** — pre-built, no manual install required
- **Linked QCOW2 clones** — base images are preserved; instances are disposable
- **Isolated network** — VMs talk to each other, not your LAN
- **Checksum verification** — downloaded images are verified before conversion
- **Clean teardown** — `--destroy` removes VMs, disks, and network in one shot

---

## How It Works

Zertana works in two steps:
- first build your VulnHub database using [owleye](https://github.com/t3rtz4/owleye)
- then deploy your lab with Zertana.

```
owleye                        zertana
──────────────────────        ──────────────────────────────────────────
Scrapes VulnHub         ───►  Interactive wizard  ──►  Blueprint
Saves machines_db.json        │
github.com/t3rtz4/owleye      ├──► Download + convert target image
                              ├──► Download Kali QEMU image
                              ├──► Create isolated network (10.10.10.0/24)
                              └──► Deploy VMs via libvirt           
```

---

## Requirements

| Dependency | Purpose |
|---|---|
| KVM/QEMU | Hypervisor |
| libvirt + virt-manager | VM management |
| `qemu-img` | Image conversion |
| `7z` | Kali image extraction |
| Python 3.11+ | Runtime |

### Install system dependencies (Fedora)

```bash
sudo dnf install -y \
    @virtualization \
    qemu-img \
    p7zip p7zip-plugins \
    libvirt \
    virt-manager

sudo systemctl enable --now libvirtd
sudo usermod -aG libvirt,kvm $USER   # re-login after this
```

---

## Installation

```bash
git clone https://github.com/yourname/zertana.git
cd zertana
pip install .
```

---

## Usage

### Step 1 — Build the VulnHub database

Install and run [owleye](https://github.com/t3rtz4/owleye) to populate
the machine database that Zertana reads from:

```bash
pip install git+https://github.com/t3rtz4/owleye.git
owleye
```

This saves machine metadata to `~/.config/zertana/machines_db.json` —
the same path Zertana expects. Run it once, then update it periodically
as new VulnHub machines are released.

```bash
owleye --max-pages 5      # scrape first 5 pages only
owleye --concurrency 8    # increase parallel requests
```

### Step 2 — Deploy a lab

```bash
zertana
```

The interactive wizard will walk you through:
1. Optionally deploying a Kali attack box
2. Selecting a VulnHub target via fuzzy search
3. Configuring RAM and vCPUs for each VM
4. Confirming and deploying the blueprint

### Step 3 — Tear down

```bash
zertana --destroy <vm-name>         # destroy a target VM
```

---

## Network Layout

All VMs are placed on an isolated private network with no access to your LAN or the internet.

```
  ┌─────────────────────────────────────────────┐
  │          zertana_net (isolated)             │
  │              10.10.10.0/24                  │
  │                                             │
  │   ┌──────────────┐    ┌──────────────────┐  │
  │   │ kali-attacker│    │  VulnHub Target  │  │
  │   │ 10.10.10.x   │    │  10.10.10.y      │  │
  │   └──────────────┘    └──────────────────┘  │
  └─────────────────────────────────────────────┘
               (no host LAN access)
```

---

## Kali Attack Box

Zertana uses the **official Kali Linux QEMU image** from Offensive Security. The base image is downloaded once (~3GB) and reused for all instances via linked clones.

After first boot, enable the SPICE display agent inside Kali for proper resolution support:

```bash
sudo systemctl enable --now spice-vdagentd
```

Default credentials: `kali / kali` — change them after first login.

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

---

## Roadmap

- [ ] `--list` command to show running Zertana VMs and IPs
- [ ] Metasploitable 2/3 as a builtin static target
- [ ] Windows target support (evaluation ISO + unattended install)
- [ ] Active Directory lab bundle (GOAD integration)
- [ ] TUI dashboard

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

Bug reports and feature requests → [GitHub Issues](https://github.com/yourname/zertana/issues)

---

## Disclaimer

Zertana is intended for **legal, ethical security research and learning** in isolated local environments. Do not use it to attack systems you do not own or have explicit permission to test.

---

## License

MIT — see [LICENSE](LICENSE)
