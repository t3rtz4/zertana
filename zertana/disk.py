import hashlib
import re
import tarfile
import subprocess
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import Progress, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

console = Console()

IMAGES_DIR     = Path("/var/lib/libvirt/images/zertana_labs")
CHUNK_SIZE     = 8192
QEMU_TIMEOUT   = 300
SUPPORTED_FMTS = {"OVA", "VMDK"}
KALI_QEMU_URL  = "https://cdimage.kali.org/current/kali-linux-2025.4-qemu-amd64.7z"
KALI_IMAGE_DIR = IMAGES_DIR / "kali"

def download_image(url: str, dest_path: Path, label: str = "Downloading...") -> None:
    console.print(f"[cyan]Downloading from: {url}[/cyan]")

    with httpx.Client(follow_redirects=True) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))

            with Progress(
                "[progress.description]{task.description}",
                "[progress.percentage]{task.percentage:>3.0f}%",
                DownloadColumn(),
                TransferSpeedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task(f"[green]{label}", total=total_size)

                with open(dest_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=CHUNK_SIZE):
                        f.write(chunk)
                        progress.update(task, advance=len(chunk))


def verify_checksum(file_path: Path, expected: str, algorithm: str = "md5") -> bool:
    """
    Verifies the file's hash against the expected value.
    Returns True if they match, False otherwise.
    """
    console.print(f"[cyan]Verifying {algorithm.upper()} checksum...[/cyan]")
    h = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)

    if h.hexdigest().lower() == expected.lower():
        console.print(f"[green]Checksum OK ({algorithm.upper()}).[/green]")
        return True

    console.print(
        f"[red]Checksum mismatch ({algorithm.upper()})! "
        f"Expected {expected}, got {h.hexdigest()}. File may be corrupted.[/red]"
    )
    return False


def _run_checksum_verification(file_path: Path, download_info: dict) -> bool:
    """
    Picks the best available checksum from owleye's DB schema:
        download_info.checksums = { "md5": "...", "sha1": "..." }
    Prefers SHA1 over MD5. Skips silently if none are available.
    """
    checksums = download_info.get("checksums", {})

    for algo in ("sha1", "md5"):
        expected = checksums.get(algo, "Unknown")
        if expected and expected != "Unknown":
            return verify_checksum(file_path, expected, algo)

    console.print("[yellow]No checksum available — skipping verification.[/yellow]")
    return True


def _assert_supported_format(download_info: dict) -> bool:
    """
    Rejects unsupported formats (ZIP, 7Z) before any download attempt.
    disk.py only handles OVA and raw VMDK.
    """
    fmt = download_info.get("format", "").upper()
    if fmt not in SUPPORTED_FMTS:
        console.print(
            f"[red]Unsupported format '{fmt}'. "
            f"Zertana only supports: {', '.join(sorted(SUPPORTED_FMTS))}.[/red]"
        )
        return False
    return True


def _safe_extract_vmdk(tar: tarfile.TarFile, member: tarfile.TarInfo, work_dir: Path) -> None:
    if ".." in member.name or member.name.startswith("/"):
        raise ValueError(f"Unsafe path in archive: {member.name}")
    tar.extract(member, path=work_dir)


def extract_and_convert_ova(ova_path: Path, base_qcow2_path: Path) -> bool:
    work_dir  = ova_path.parent
    vmdk_path = None

    console.print("[cyan]Extracting OVA archive...[/cyan]")
    try:
        with tarfile.open(ova_path, "r") as tar:
            vmdk_members = [m for m in tar.getmembers() if m.name.endswith(".vmdk")]
            if not vmdk_members:
                console.print("[red]No VMDK disk found inside the OVA.[/red]")
                return False

            target_vmdk = vmdk_members[0]
            _safe_extract_vmdk(tar, target_vmdk, work_dir)
            vmdk_path = work_dir / target_vmdk.name

        console.print(f"[cyan]Converting {target_vmdk.name} to QCOW2...[/cyan]")
        _convert_vmdk_to_qcow2(vmdk_path, base_qcow2_path)
        console.print(f"[green]Base image created: {base_qcow2_path.name}[/green]")

    except ValueError as e:
        console.print(f"[red]Archive extraction blocked: {e}[/red]")
        return False
    except subprocess.CalledProcessError as e:
        console.print(f"[red]qemu-img conversion failed: {e.stderr.decode().strip()}[/red]")
        return False
    except subprocess.TimeoutExpired:
        console.print(f"[red]qemu-img timed out after {QEMU_TIMEOUT}s.[/red]")
        return False
    finally:
        if vmdk_path and vmdk_path.exists():
            vmdk_path.unlink()
        if ova_path.exists():
            ova_path.unlink()
        console.print("[dim]Temporary files cleaned up.[/dim]")

    return True


def _convert_vmdk_to_qcow2(vmdk_path: Path, qcow2_path: Path) -> None:
    cmd = [
        "qemu-img", "convert",
        "-f", "vmdk",
        "-O", "qcow2",
        str(vmdk_path),
        str(qcow2_path),
    ]
    subprocess.run(cmd, check=True, timeout=QEMU_TIMEOUT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def convert_vmdk_to_qcow2(vmdk_path: Path, base_qcow2_path: Path) -> bool:
    """
    Converts a bare VMDK (not inside an OVA) directly to QCOW2.
    Used when owleye reports format = VMDK.
    """
    console.print(f"[cyan]Converting {vmdk_path.name} to QCOW2...[/cyan]")
    try:
        _convert_vmdk_to_qcow2(vmdk_path, base_qcow2_path)
        console.print(f"[green]Base image created: {base_qcow2_path.name}[/green]")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]qemu-img conversion failed: {e.stderr.decode().strip()}[/red]")
        return False
    except subprocess.TimeoutExpired:
        console.print(f"[red]qemu-img timed out after {QEMU_TIMEOUT}s.[/red]")
        return False
    finally:
        if vmdk_path.exists():
            vmdk_path.unlink()
        console.print("[dim]Temporary VMDK cleaned up.[/dim]")
    return True

def extract_7z_image(archive_path: Path, dest_dir: Path) -> Path | None:
    """
    Extracts a Kali .7z archive and returns the path to the extracted .qcow2.
    Uses the system 7z binary since Python's lzma module doesn't handle .7z format.
    """
    console.print("[cyan]Extracting Kali image archive...[/cyan]")
    try:
        subprocess.run(
            ["7z", "x", str(archive_path), f"-o{dest_dir}", "-y"],
            check=True,
            timeout=QEMU_TIMEOUT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as e:
        console.print(f"[red]7z extraction failed: {e.stderr.decode().strip()}[/red]")
        return None
    except subprocess.TimeoutExpired:
        console.print(f"[red]7z extraction timed out after {QEMU_TIMEOUT}s.[/red]")
        return None
    finally:
        archive_path.unlink(missing_ok=True)
        console.print("[dim]Archive cleaned up.[/dim]")

    # Find the extracted .qcow2
    qcow2_files = list(dest_dir.glob("*.qcow2"))
    if not qcow2_files:
        console.print("[red]No .qcow2 found after extraction.[/red]")
        return None

    console.print(f"[green]Extracted: {qcow2_files[0].name}[/green]")
    return qcow2_files[0]


def _create_linked_clone(base_qcow2: Path, instance_qcow2: Path) -> bool:
    cmd = [
        "qemu-img", "create",
        "-f", "qcow2",
        "-b", str(base_qcow2),
        "-F", "qcow2",
        str(instance_qcow2),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=QEMU_TIMEOUT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to create linked clone: {e.stderr.decode().strip()}[/red]")
        return False
    except subprocess.TimeoutExpired:
        console.print(f"[red]Linked clone creation timed out after {QEMU_TIMEOUT}s.[/red]")
        return False
    return True


def prepare_target_image(blueprint: dict) -> str | None:
    target_info = blueprint.get("target")
    if not target_info:
        console.print("[red]No target found in blueprint.[/red]")
        return None

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    vm_name       = target_info["vm_name"]
    vulnhub_name  = target_info["target_data"]["name"]
    download_info = target_info["target_data"]["download_info"]
    download_url  = download_info["url"]
    fmt           = download_info.get("format", "").upper()

    # Reject unsupported formats before touching the network
    if not _assert_supported_format(download_info):
        return None

    clean_base_name = re.sub(r"[^a-zA-Z0-9_-]", "_", vulnhub_name)
    base_qcow2      = IMAGES_DIR / f"{clean_base_name}_base.qcow2"
    instance_qcow2  = IMAGES_DIR / f"{vm_name}_instance.qcow2"

    # Determine the correct download extension and converter
    ext      = ".ova"  if fmt == "OVA"  else ".vmdk"
    dl_label = "Downloading OVA..." if fmt == "OVA" else "Downloading VMDK..."
    dl_path  = IMAGES_DIR / f"{clean_base_name}{ext}"

    if not base_qcow2.exists():
        console.print(f"[yellow]Base image not found. Downloading {vulnhub_name}...[/yellow]")
        try:
            download_image(download_url, dl_path, label=dl_label)

            # Verify integrity before doing anything with the file
            if not _run_checksum_verification(dl_path, download_info):
                dl_path.unlink(missing_ok=True)
                return None

            # Convert to base QCOW2
            if fmt == "OVA":
                success = extract_and_convert_ova(dl_path, base_qcow2)
            else:
                success = convert_vmdk_to_qcow2(dl_path, base_qcow2)

        except Exception as e:
            dl_path.unlink(missing_ok=True)
            console.print(f"[red]Download or conversion failed: {e}[/red]")
            return None

        if not success:
            return None
    else:
        console.print(f"[green]Base image already exists: {base_qcow2.name}[/green]")

    if instance_qcow2.exists():
        console.print(f"[yellow]Instance disk for '{vm_name}' already exists. It will be overwritten.[/yellow]")

    console.print(f"[cyan]Creating linked clone for '{vm_name}'...[/cyan]")
    if not _create_linked_clone(base_qcow2, instance_qcow2):
        return None

    console.print(f"[green]Instance disk ready: {instance_qcow2.name}[/green]")
    return str(instance_qcow2)

def prepare_attacker_image(vm_name: str) -> str | None:
    """
    Downloads the official Kali QEMU image if not already present,
    then creates a linked clone for the attacker VM instance.
    """
    KALI_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    base_qcow2     = KALI_IMAGE_DIR / "kali_base.qcow2"
    instance_qcow2 = KALI_IMAGE_DIR / f"{vm_name}_instance.qcow2"
    archive_path   = KALI_IMAGE_DIR / "kali.7z"

    if not base_qcow2.exists():
        console.print("[yellow]Kali base image not found. Downloading official QEMU image...[/yellow]")
        console.print("[dim]This is a large download (~3GB). Please be patient.[/dim]")

        try:
            download_image(KALI_QEMU_URL, archive_path, label="Downloading Kali QEMU image...")
        except Exception as e:
            archive_path.unlink(missing_ok=True)
            console.print(f"[red]Kali download failed: {e}[/red]")
            return None

        extracted = extract_7z_image(archive_path, KALI_IMAGE_DIR)
        if not extracted:
            return None

        # Rename to a stable base name
        extracted.rename(base_qcow2)
        console.print(f"[green]Kali base image ready: {base_qcow2.name}[/green]")
    else:
        console.print(f"[green]Kali base image already exists: {base_qcow2.name}[/green]")

    if instance_qcow2.exists():
        console.print(f"[yellow]Attacker instance for '{vm_name}' already exists. It will be overwritten.[/yellow]")

    console.print(f"[cyan]Creating linked clone for '{vm_name}'...[/cyan]")
    if not _create_linked_clone(base_qcow2, instance_qcow2):
        return None

    console.print(f"[green]Attacker instance disk ready: {instance_qcow2.name}[/green]")
    return str(instance_qcow2)
