import shutil
import psutil
import libvirt
from rich.console import Console

libvirt.registerErrorHandler(f=lambda ctx, err: None, ctx=None)

console = Console()

MIN_RAM_GB = 2.0 # We will need (4GB) for the whole lab, 2GB is good for the target machine only
MIN_DISK_GB = 10.0 
LIBVIRT_IMAGES_PATH = "/var/lib/libvirt/images"


def check_system_resources() -> bool:
    mem = psutil.virtual_memory()
    free_ram_gb = mem.available / (1024 ** 3)

    if free_ram_gb < MIN_RAM_GB:
        console.print(f"[red]Insufficient RAM: {free_ram_gb:.1f}GB available, {MIN_RAM_GB}GB required.[/red]")
        return False
    console.print(f"[green]RAM: {free_ram_gb:.1f}GB available.[/green]")

    try:
        free_disk_gb = shutil.disk_usage(LIBVIRT_IMAGES_PATH).free / (1024 ** 3)
        if free_disk_gb < MIN_DISK_GB:
            console.print(f"[red]Insufficient disk space: {free_disk_gb:.1f}GB available in {LIBVIRT_IMAGES_PATH}, {MIN_DISK_GB}GB required.[/red]")
            return False
        console.print(f"[green]Disk: {free_disk_gb:.1f}GB available.[/green]")
    except FileNotFoundError:
        console.print(f"[yellow]Libvirt images path not found ({LIBVIRT_IMAGES_PATH}). Skipping disk check.[/yellow]")

    return True


def check_qemu_tools() -> bool:
    missing = [tool for tool in ("qemu-img", "qemu-system-x86_64", "genisoimage") if not shutil.which(tool)]
    if missing:
        console.print(f"[red]Missing required tools: {', '.join(missing)}. Install qemu-utils and qemu-system.[/red]")
        return False
    console.print("[green]QEMU tools found.[/green]")
    return True


def check_kvm_readiness() -> bool:
    try:
        conn = libvirt.open("qemu:///system")
        if conn is None:
            console.print("[red]Could not connect to qemu:///system.[/red]")
            return False

        hostname = conn.getHostname()
        conn.close()
        console.print(f"[green]Hypervisor: Connected to {hostname} (QEMU/KVM).[/green]")
        return True

    except libvirt.libvirtError as e:
        console.print(f"[red]KVM/Libvirt connection failed: {e}[/red]")
        console.print("[yellow]Possible fixes:[/yellow]")
        console.print("  - Start the daemon:      sudo systemctl start libvirtd")
        console.print("  - Add user to groups:    sudo usermod -aG libvirt,kvm $USER  (requires re-login)")
        return False


def run_preflight() -> bool:
    console.print("[bold cyan]Pre-flight checks[/bold cyan]\n")

    checks = [
        ("System resources", check_system_resources),
        ("QEMU tools",       check_qemu_tools),
        ("KVM/Libvirt",      check_kvm_readiness),
    ]

    for label, check in checks:
        console.print(f"[cyan]{label}...[/cyan]")
        if not check():
            console.print(f"\n[red]Pre-flight failed at: {label}[/red]")
            return False
        console.print()

    console.print("[green]All checks passed. Ready to deploy.[/green]\n")
    return True
