import sys
import argparse
from rich.console import Console
from rich.table import Table
from InquirerPy import inquirer

from .checks import run_preflight
from .wizard import get_attack_box_config, get_target_config
from .disk import prepare_target_image, prepare_attacker_image
from .hypervisor import deploy_isolated_lab, deploy_attacker, teardown_lab, get_vm_ip

console = Console()

ZERTANA_BANNER = r"""[bold magenta]
███████╗███████╗██████╗ ████████╗█████╗ ███╗   ██╗█████╗
╚══███╔╝██╔════╝██╔══██╗╚══██╔══╝██╔══██╗████╗  ██║██╔══██╗
  ███╔╝ █████╗  ██████╔╝   ██║   ███████║██╔██╗ ██║███████║
 ███╔╝  ██╔══╝  ██╔══██╗   ██║   ██╔══██║██║╚██╗██║██╔══██║
███████╗███████╗██║  ██║   ██║   ██║  ██║██║ ╚████║██║  ██║
╚══════╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝[/bold magenta]
                [bold cyan]Your personal CTF lab builder[/bold cyan]
"""


def generate_lab_blueprint() -> dict:
    console.print(ZERTANA_BANNER)

    if not run_preflight():
        console.print("[red]Pre-flight checks failed. Fix the issues above and try again.[/red]")
        sys.exit(1)

    attack_config = get_attack_box_config()
    target_config = get_target_config()

    if not attack_config and not target_config:
        console.print("[yellow]Nothing selected. Exiting.[/yellow]")
        sys.exit(0)

    blueprint = {
        "attack_box": attack_config,
        "target":     target_config,
    }

    console.print("\n[bold green]Blueprint Summary[/bold green]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Node Type", style="cyan", width=15)
    table.add_column("VM Name",   style="white")
    table.add_column("Resources", style="yellow")
    table.add_column("Details",   style="white")

    if attack_config:
        table.add_row(
            "Attack Box",
            attack_config.get("vm_name", "kali-attacker"),
            f"{attack_config['vcpus']} vCPUs | {attack_config['ram']}MB RAM",
        )
    else:
        table.add_row("Attack Box", "[dim]Skipped (using host)[/dim]", "-", "-")

    if target_config:
        t_data = target_config["target_data"]
        table.add_row(
            "Target",
            target_config["vm_name"],
            f"{target_config['vcpus']} vCPUs | {target_config['ram_mb']}MB RAM | {t_data['download_info'].get('size', 'Unknown')}",
            t_data["name"],
        )
    else:
        table.add_row("Target", "[dim]Skipped[/dim]", "-", "-")

    console.print(table)
    console.print()

    if not inquirer.confirm(message="Deploy this blueprint?", default=True).execute():
        console.print("[yellow]Deployment cancelled. No changes were made.[/yellow]")
        sys.exit(0)

    console.print("\n[cyan]Starting deployment...[/cyan]\n")
    return blueprint


def _prepare_target(blueprint: dict) -> str:
    image_path = prepare_target_image(blueprint)
    if not image_path:
        console.print("[red]Failed to prepare target image. Aborting.[/red]")
        sys.exit(1)
    console.print(f"[green]Target image ready: {image_path}[/green]\n")
    return image_path

def _print_lab_summary(attack_config: dict | None, target_config: dict | None) -> None:
    """Prints a final summary table with VM names and their IPs."""
    console.print("\n[bold green]Lab Summary[/bold green]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Role",    style="cyan",  width=15)
    table.add_column("VM Name", style="white", width=20)
    table.add_column("IP",      style="green")

    if attack_config:
        ip = get_vm_ip(attack_config["vm_name"]) or "[yellow]Pending...[/yellow]"
        table.add_row("Attacker", attack_config["vm_name"], ip)

    if target_config:
        ip = get_vm_ip(target_config["vm_name"]) or "[yellow]Pending...[/yellow]"
        table.add_row("Target", target_config["vm_name"], ip)

    console.print(table)
    console.print(
        "\n[yellow]Tip: Enable spice-vdagentd inside Kali for proper resolution support:[/yellow]"
        "\n  [dim]sudo systemctl enable --now spice-vdagentd[/dim]\n"
        if attack_config else ""
    )


def main():
    parser = argparse.ArgumentParser(description="Zertana: CTF Lab Builder")
    parser.add_argument("--destroy", metavar="VM_NAME", help="Destroy a VM and clean up its network", type=str)
    args = parser.parse_args()

    if args.destroy:
        teardown_lab(vm_name=args.destroy)
        sys.exit(0)

    try:
        blueprint     = generate_lab_blueprint()
        attack_config = blueprint.get("attack_box")
        target_config = blueprint.get("target")

        # Scenario 1: Attack Box only
        if attack_config and not target_config:
            console.print("[bold magenta]Scenario: Attack Box only.[/bold magenta]\n")

            image_path = prepare_attacker_image(attack_config["vm_name"])
            if not image_path:
                console.print("[red]Failed to prepare Kali image. Aborting.[/red]")
                sys.exit(1)

            success = deploy_attacker(
                attack_config["vm_name"],
                image_path,
                ram_mb=attack_config["ram"],
                vcpus=attack_config["vcpus"],
            )
            if not success:
                sys.exit(1)

            _print_lab_summary(attack_config, None)

        # Scenario 2: Target only
        elif target_config and not attack_config:
            console.print("[cyan]Scenario: Target only.[/cyan]\n")

            image_path = _prepare_target(blueprint)
            success = deploy_isolated_lab(
                target_config["vm_name"],
                image_path,
                ram_mb=target_config["ram_mb"],
                vcpus=target_config["vcpus"],
            )
            if not success:
                sys.exit(1)

            _print_lab_summary(None, target_config)

        # Scenario 3: Full lab (Attack Box + Target)
        else:
            console.print("[bold magenta]Scenario: Full lab (Attack Box + Target).[/bold magenta]\n")

            image_path = _prepare_target(blueprint)
            success = deploy_isolated_lab(
                target_config["vm_name"],
                image_path,
                ram_mb=target_config["ram_mb"],
                vcpus=target_config["vcpus"],
            )
            if not success:
                sys.exit(1)

            kali_image = prepare_attacker_image(attack_config["vm_name"])
            if not kali_image:
                console.print("[red]Failed to prepare Kali image. Aborting.[/red]")
                sys.exit(1)

            success = deploy_attacker(
                attack_config["vm_name"],
                kali_image,
                ram_mb=attack_config["ram"],
                vcpus=attack_config["vcpus"],
            )
            if not success:
                sys.exit(1)

            _print_lab_summary(attack_config, target_config)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Exiting cleanly.[/yellow]")
        sys.exit(0)


if __name__ == "__main__":
    main()
