# Zertana 🦉

[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)](https://kernel.org/)
[![owleye](https://img.shields.io/badge/companion-owleye-blueviolet)](https://github.com/t3rtz4/owleye)

> Your personal CTF lab builder, powered by KVM/QEMU

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

## What is Zertana?

Zertana is a command-line tool that builds fully isolated penetration testing labs on your own machine. It automates the tedious parts of lab setup: downloading vulnerable virtual machines from VulnHub, spinning up a Kali Linux attacker box, and connecting everything on a private sandboxed network that is completely separated from your real LAN.

The goal is to let you go from zero to an active lab with a single command. No manual VM configuration, no messing with networking, no waiting around for images to be set up by hand. Zertana handles all of that for you.

Zertana is built for security learners, OSCP candidates, and CTF enthusiasts who want a repeatable, clean way to spin up and tear down practice targets without ever touching their host machine's network.

---

## Features

**One-command lab setup.** Run `zertana` and an interactive wizard walks you through the entire process. Within a few minutes you have an attacker box and a vulnerable target both running and connected to each other.

**VulnHub integration.** Zertana works with a local database of VulnHub machines (built by the companion tool [owleye](https://github.com/t3rtz4/owleye)). You search for a target by name using fuzzy matching, and Zertana downloads and configures the image automatically.

**Official Kali QEMU image.** Zertana downloads the official Kali Linux image from Offensive Security. You do not need to install Kali manually or find a compatible image yourself. The base image is downloaded once and reused across all your labs.

**Linked QCOW2 clones.** When Zertana creates a new VM instance, it creates a lightweight linked clone of the base disk image rather than copying the entire image. This saves significant disk space and makes spinning up new instances much faster. The original base image is never modified.

**Fully isolated network.** All VMs in a Zertana lab are placed on a private virtual network (`10.10.10.0/24`) with no routing to your host machine's real network or the internet. Your attack traffic stays completely contained.

**Checksum verification.** Every downloaded image is verified against its checksum before Zertana attempts to convert or use it. This protects you from corrupted downloads silently causing problems later.

**Clean teardown.** When you are done, a single `--destroy` command removes the VMs, their disk images, and the virtual network, leaving no leftover state on your system.

---

## How It Works

Zertana is designed around a two-step workflow. First you build a local database of available VulnHub machines using the companion tool owleye. Then you use that database to select and deploy targets.

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

**Why two steps?** Owleye scrapes VulnHub and saves machine metadata (names, download URLs, descriptions) to a local JSON file at `~/.config/zertana/machines_db.json`. Keeping this step separate means Zertana does not need to hit VulnHub's website every time you start a lab. You run owleye once to build the database, then refresh it periodically to pick up newly added machines.

When you run `zertana`, it reads the database, presents an interactive wizard, and builds a deployment blueprint. It then executes that blueprint: downloading and converting any images that are not cached, creating a libvirt virtual network, and defining and starting each VM via the KVM hypervisor.

---

## Requirements

Zertana relies on standard Linux virtualization tooling. All of the following must be present on your system.

| Dependency | Purpose |
|---|---|
| KVM/QEMU | The hypervisor that runs the virtual machines |
| libvirt + virt-manager | API layer for creating and managing VMs and networks |
| `qemu-img` | Converts downloaded images to QCOW2 format and creates linked clones |
| `7z` | Extracts the Kali QEMU image archive (it ships as a `.7z` file) |
| Python 3.11+ | Runtime for Zertana itself |

Your CPU must support hardware virtualization (Intel VT-x or AMD-V) and it must be enabled in your BIOS/UEFI. You can verify this by checking that `/dev/kvm` exists on your system.

### Installing system dependencies on Fedora

```bash
sudo dnf install -y \
    @virtualization \
    qemu-img \
    p7zip p7zip-plugins \
    libvirt \
    virt-manager

sudo systemctl enable --now libvirtd
sudo usermod -aG libvirt,kvm $USER
```

After running `usermod`, you need to log out and back in for the group membership to take effect. Without being in the `libvirt` and `kvm` groups, Zertana will not be able to connect to the hypervisor or create VMs.

---

## Installation

```bash
git clone https://github.com/t3rtz4/zertana.git
cd zertana
pip install .
```

This installs the `zertana` command into your Python environment. You can also use `pip install -e .` if you want an editable install for development.

---

## Usage

### Step 1: Build the VulnHub database

Install and run [owleye](https://github.com/t3rtz4/owleye) to populate the machine database that Zertana reads from.

```bash
pip install git+https://github.com/t3rtz4/owleye.git
owleye
```

Owleye will scrape VulnHub and save machine metadata to `~/.config/zertana/machines_db.json`. This is the path Zertana expects to find the database. Run this command once to get started, and re-run it periodically to pick up newly published VulnHub machines.

If you want to limit how much of VulnHub gets scraped (for example during testing), you can control the scrape depth and speed:

```bash
owleye --max-pages 5      # scrape only the first 5 pages
owleye --concurrency 8    # increase the number of parallel requests
```

### Step 2: Deploy a lab

```bash
zertana
```

The interactive wizard will walk you through four decisions:

1. **Attacker box.** Choose whether to deploy a Kali Linux VM as your attack machine. If you already have a preferred attacker setup, you can skip this.
2. **Target selection.** Search for a VulnHub machine by name using fuzzy search. Type part of the name and Zertana will narrow down the options.
3. **Resource configuration.** Set the amount of RAM and the number of virtual CPU cores for each VM. Defaults are provided but you can tune them based on your hardware.
4. **Confirmation.** Review the deployment blueprint and confirm before anything is downloaded or created.

### Step 3: Tear down

When you are done with a lab, remove it completely with:

```bash
zertana --destroy <vm-name>
```

This deletes the VM definition, the linked clone disk image, and the associated virtual network. Your base images (Kali and any cached VulnHub targets) are preserved for future use.

---

## Network Layout

Every lab runs on a dedicated isolated virtual network. The VMs can communicate with each other freely, but they have no route to your real LAN or to the internet. This keeps your attack traffic contained and ensures the target VM cannot reach anything it should not.

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

The network is created fresh for each lab and removed when you run `--destroy`. IPs are assigned by the virtual network's DHCP server.

---

## The Kali Attack Box

Zertana sources its Kali image from the official Offensive Security QEMU image. This is the same image that Offensive Security maintains for use with QEMU/KVM, so it is guaranteed to be compatible.

The base image is approximately 3 GB and is downloaded only once. Every time you create a new lab, Zertana creates a linked QCOW2 clone from that base image rather than downloading or copying it again. This means the first lab takes longer (the download), but subsequent labs are fast.

After your first boot into Kali, run the following inside the VM to enable the SPICE display agent. This gives you proper screen resolution support when viewing the VM through virt-manager or a SPICE client:

```bash
sudo systemctl enable --now spice-vdagentd
```

The default login credentials are `kali` for both the username and password. Change your password after the first login.

---

## Project Structure

The codebase is small and focused. Each module has a single well-defined responsibility.

```
zertana/
├── cli.py          # Entry point: argument parsing and scenario orchestration
├── checks.py       # Preflight checks: RAM, disk space, QEMU tools, KVM connectivity
├── wizard.py       # Interactive configuration prompts (powered by InquirerPy)
├── disk.py         # Image downloading, extraction, format conversion, and linked clone creation
└── hypervisor.py   # libvirt interactions: virtual network and VM creation, startup, and teardown
```

**`cli.py`** is the entry point. It parses command-line arguments and decides which scenario to run (interactive deploy or destroy).

**`checks.py`** runs before any lab work starts. It verifies that you have enough free RAM and disk space, that the required QEMU tools are installed, and that a connection to libvirt is available. Any failures here produce a clear error message before anything destructive happens.

**`wizard.py`** drives the interactive setup flow using InquirerPy. It collects your choices (target, resources, options) and returns a structured blueprint.

**`disk.py`** handles all image lifecycle operations: downloading from a URL, verifying checksums, converting to QCOW2 format with `qemu-img`, and creating lightweight linked clones for new instances.

**`hypervisor.py`** talks to libvirt to create the isolated virtual network, define VM configurations as libvirt XML, start the VMs, and handle clean teardown.

---

## Roadmap

- `--list` command to show all running Zertana VMs and their assigned IP addresses
- Metasploitable 2/3 as a built-in static target that does not require owleye
- Windows target support using evaluation ISOs with unattended installation
- Active Directory lab bundle via GOAD integration
- TUI dashboard for monitoring running labs

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

Bug reports and feature requests go in [GitHub Issues](https://github.com/t3rtz4/zertana/issues).

---

## Disclaimer

Zertana is intended for legal, ethical security research and learning in isolated local environments. Only use it to test systems that you own or have been given explicit written permission to test. Do not use it to attack systems belonging to others.

---

## License

MIT. See [LICENSE](LICENSE) for the full text.
