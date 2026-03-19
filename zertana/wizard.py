import re
import json
from pathlib import Path
from InquirerPy import inquirer
from InquirerPy.validator import NumberValidator
from rich.console import Console

console = Console()

DB_PATH = Path.home() / ".config" / "zertana" / "machines_db.json"

MIN_DISK_GB = 10
MIN_RAM_MB  = 2048

def get_attack_box_config() -> dict | None:
    console.print("\n[bold cyan]Attack Box Configuration[/bold cyan]\n")

    if not inquirer.confirm(
        message="Deploy an isolated Kali Linux attack box ?",
        default=False
    ).execute():
        console.print("[yellow]Skipping attack box. Host machine will be used.[/yellow]\n")
        return None

    ram_mb = inquirer.text(
        message=f"RAM in MB (min {MIN_RAM_MB}, recommended 4096):",
        default="2048",
        validate=NumberValidator(message="Enter a valid number."),
        filter=lambda r: int(r)
    ).execute()

    vcpus = inquirer.text(
        message="vCPUs (recommended 2):",
        default="2",
        validate=NumberValidator(message="Enter a valid number."),
        filter=lambda r: int(r)
    ).execute()

    disk_gb = inquirer.text(
        message=f"Disk space in GB (min {MIN_DISK_GB}, recommended 20):",
        default="20",
        validate=NumberValidator(message="Enter a valid number."),
        filter=lambda r: int(r)
    ).execute()

    if disk_gb < MIN_DISK_GB:
        console.print(f"[yellow]Disk size below minimum. Forcing {MIN_DISK_GB}GB.[/yellow]")
        disk_gb = MIN_DISK_GB

    if ram_mb < MIN_RAM_MB:
        console.print(f"[yellow]RAM below minimum. Forcing {MIN_RAM_MB}MB.[/yellow]")
        ram_mb = MIN_RAM_MB

    config = {
        "vm_name": "kali-attacker",
        "deploy":  True,
        "ram":     ram_mb,
        "vcpus":   vcpus,
        "disk_gb": disk_gb,
    }

    console.print(
        f"[green]Attack box: {vcpus} vCPUs, {ram_mb}MB RAM, {disk_gb}GB disk.[/green]\n"
    )

    return config


def _load_target_db() -> list | None:
    if not DB_PATH.exists():
        console.print(f"[red]Target database not found at {DB_PATH}.[/red]")
        console.print("[yellow]Run the 'owleye' scraper first to generate it.[/yellow]")
        return None

    try:
        with open(DB_PATH, "r") as f:
            db_data = json.load(f)
    except json.JSONDecodeError:
        console.print("[red]Database file is corrupted. Re-run 'owleye' to regenerate it.[/red]")
        return None

    targets = db_data.get("targets", [])

    if not targets:
        console.print("[red]No targets found in the database.[/red]")
        return None

    SUPPORTED_FMTS = {"OVA", "VMDK"}

    targets = [
        t for t in targets
        if t.get("download_info", {}).get("format", "").upper() in SUPPORTED_FMTS
    ]

    if not targets:
        console.print("[red]No supported targets (OVA/VMDK) found in the database.[/red]")
        return None

    return targets


def get_target_config() -> dict | None:
    console.print("\n[bold cyan]Target Machine Selection[/bold cyan]\n")

    if not inquirer.confirm(
        message="Do you want to deploy a Target machine (VulnHub) ?",
        default=True
    ).execute():
        console.print("[yellow]Skipping target machine.[/yellow]\n")
        return None

    targets = _load_target_db()
    if targets is None:
        return None

    choices = [
        {
            "name":  f"{t.get('name', 'Unknown')} | {t.get('download_info', {}).get('size', 'Unknown')}",
            "value": t,
        }
        for t in targets
    ]

    selected = inquirer.fuzzy(
        message="Select a target machine:",
        choices=choices,
        max_height="70%",
        instruction="(Type to filter, Enter to select)"
    ).execute()

    console.print(f"[green]Selected: {selected['name']}[/green]")

    default_vm_name = re.sub(r"[^a-zA-Z0-9_-]", "_", selected["name"])

    vm_name = inquirer.text(
        message="VM name in KVM:",
        default=default_vm_name
    ).execute()

    ram_mb = inquirer.text(
        message="RAM for target VM in MB (recommended 1024):",
        default="1024",
        validate=NumberValidator(message="Enter a valid number."),
        filter=lambda r: int(r)
    ).execute()

    vcpus = inquirer.text(
        message="vCPUs for target VM (recommended 1):",
        default="1",
        validate=NumberValidator(message="Enter a valid number."),
        filter=lambda r: int(r)
    ).execute()

    config = {
        "vm_name":     vm_name,
        "ram_mb":      ram_mb,
        "vcpus":       vcpus,
        "target_data": selected,
    }

    return config
