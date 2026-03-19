import os
import shutil
import sys
from pathlib import Path
import libvirt
from rich.console import Console

from .disk import IMAGES_DIR

libvirt.registerErrorHandler(f=lambda ctx, err: None, ctx=None)

console = Console()

NET_NAME    = "zertana_net"
LIBVIRT_URI = "qemu:///system"


def get_connection() -> libvirt.virConnect:
    try:
        conn = libvirt.open(LIBVIRT_URI)
        if conn is None:
            raise libvirt.libvirtError("libvirt.open() returned None.")
        return conn
    except libvirt.libvirtError as e:
        console.print(f"[red]Hypervisor connection failed: {e}[/red]")
        console.print("  - Start the daemon:   sudo systemctl start libvirtd")
        sys.exit(1)


def build_net_xml(net_name: str) -> str:
    return f"""<network>
  <name>{net_name}</name>
  <bridge name='virbr_zertana' stp='on' delay='0'/>
  <domain name='zertana.local'/>
  <ip address='10.10.10.1' netmask='255.255.255.0'>
    <dhcp>
      <range start='10.10.10.100' end='10.10.10.200'/>
    </dhcp>
  </ip>
</network>"""


def build_vm_xml(vm_name: str, qcow2_path: str, net_name: str, ram_mb: int = 2048, vcpus: int = 1) -> str:
    emulator = shutil.which("qemu-system-x86_64") or "/usr/bin/qemu-system-x86_64"
    return f"""<domain type='kvm'>
  <name>{vm_name}</name>
  <memory unit='MiB'>{ram_mb}</memory>
  <vcpu placement='static'>{vcpus}</vcpu>
  <os>
    <type arch='x86_64' machine='pc'>hvm</type>
    <boot dev='hd'/>
  </os>
  <devices>
    <emulator>{emulator}</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='{qcow2_path}'/>
      <target dev='hda' bus='ide'/>
    </disk>
    <interface type='network'>
      <source network='{net_name}'/>
      <model type='e1000'/>
    </interface>
    <graphics type='spice' autoport='yes'>
      <listen type='address' address='127.0.0.1'/>
    </graphics>
    <video>
      <model type='vga' vram='16384' heads='1'/>
    </video>
  </devices>
</domain>"""

def build_attacker_vm_xml(vm_name: str, qcow2_path: str, net_name: str, ram_mb: int = 2048, vcpus: int = 1) -> str:
    emulator = shutil.which("qemu-system-x86_64") or "/usr/bin/qemu-system-x86_64"
    return f"""<domain type='kvm'>
  <name>{vm_name}</name>
  <memory unit='MiB'>{ram_mb}</memory>
  <vcpu placement='static'>{vcpus}</vcpu>
  <os>
    <type arch='x86_64' machine='pc'>hvm</type>
    <boot dev='hd'/>
  </os>
  <devices>
    <emulator>{emulator}</emulator>
    <disk type='file' device='disk'>
      <driver name='qemu' type='qcow2'/>
      <source file='{qcow2_path}'/>
      <target dev='hda' bus='ide'/>
    </disk>
    <interface type='network'>
      <source network='{net_name}'/>
      <model type='e1000'/>
    </interface>
    <graphics type='spice' autoport='yes'>
      <listen type='address' address='127.0.0.1'/>
    </graphics>
    <video>
      <model type='qxl' vram='65536' heads='1'/>
    </video>
    <input type='tablet' bus='usb'/>
  </devices>
</domain>"""

def ensure_network(conn: libvirt.virConnect) -> None:
    try:
        network = conn.networkLookupByName(NET_NAME)
        if not network.isActive():
            network.create()
            console.print(f"[green]Network '{NET_NAME}' restarted.[/green]")
        else:
            console.print(f"[green]Network '{NET_NAME}' already active.[/green]")
    except libvirt.libvirtError:
        console.print(f"[cyan]Defining isolated network '{NET_NAME}'...[/cyan]")
        network = conn.networkDefineXML(build_net_xml(NET_NAME))
        network.create()
        network.setAutostart(1)
        console.print(f"[green]Network '{NET_NAME}' created and set to autostart.[/green]")


def network_has_other_vms(conn: libvirt.virConnect, net_name: str, exclude_vm: str) -> bool:
    try:
        active_ids = conn.listDomainsID()
        for dom_id in active_ids:
            dom = conn.lookupByID(dom_id)
            if dom.name() != exclude_vm and net_name in dom.XMLDesc():
                return True
    except libvirt.libvirtError:
        pass
    return False

def _get_vm_mac(dom: libvirt.virDomain) -> str | None:
    """Extract the first MAC address from a VM's XML definition."""
    import xml.etree.ElementTree as ET
    try:
        tree = ET.fromstring(dom.XMLDesc())
        mac  = tree.find(".//interface/mac")
        return mac.get("address") if mac is not None else None
    except Exception:
        return None


def get_vm_ip(vm_name: str) -> str | None:
    """Read the VM's IP from libvirt DHCP leases on zertana_net."""
    conn = get_connection()
    try:
        network = conn.networkLookupByName(NET_NAME)
        dom     = conn.lookupByName(vm_name)
        mac     = _get_vm_mac(dom)
        if not mac:
            console.print(f"[red]Could not find MAC address for '{vm_name}'.[/red]")
            return None

        for lease in network.DHCPLeases():
            if lease["mac"].lower() == mac.lower():
                return lease["ipaddr"]

        console.print(f"[yellow]No DHCP lease found for '{vm_name}' yet.[/yellow]")
        return None
    except libvirt.libvirtError as e:
        console.print(f"[red]Failed to get IP for '{vm_name}': {e}[/red]")
        return None
    finally:
        conn.close()

def deploy_isolated_lab(vm_name: str, qcow2_path: str, ram_mb: int = 2048, vcpus: int = 1) -> bool:
    console.print("\n[bold cyan]Starting provisioning...[/bold cyan]\n")

    conn = get_connection()
    try:
        ensure_network(conn)

        try:
            dom = conn.lookupByName(vm_name)
            console.print(f"[yellow]VM '{vm_name}' already exists. Rebuilding...[/yellow]")
            if dom.isActive():
                dom.destroy()
            dom.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)
        except libvirt.libvirtError:
            pass

        console.print(f"[cyan]Defining VM '{vm_name}'...[/cyan]")
        try:
            dom = conn.defineXML(build_vm_xml(vm_name, qcow2_path, NET_NAME, ram_mb, vcpus))
            dom.create()
            console.print(f"[bold green]'{vm_name}' deployed and running.[/bold green]")
            return True
        except libvirt.libvirtError as e:
            console.print(f"[red]Failed to deploy VM: {e}[/red]")
            return False
    finally:
        conn.close()

def deploy_attacker(vm_name: str, qcow2_path: str, ram_mb: int = 2048, vcpus: int = 1) -> bool:
    console.print("\n[bold cyan]Deploying Kali attack box...[/bold cyan]\n")

    conn = get_connection()
    try:
        ensure_network(conn)

        try:
            dom = conn.lookupByName(vm_name)
            console.print(f"[yellow]VM '{vm_name}' already exists. Rebuilding...[/yellow]")
            if dom.isActive():
                dom.destroy()
            dom.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)
        except libvirt.libvirtError:
            pass

        console.print(f"[cyan]Defining attacker VM '{vm_name}'...[/cyan]")
        dom = conn.defineXML(build_attacker_vm_xml(vm_name, qcow2_path, NET_NAME, ram_mb, vcpus))
        dom.create()
        console.print(f"[bold green]'{vm_name}' deployed and running.[/bold green]")
        return True

    except libvirt.libvirtError as e:
        console.print(f"[red]Failed to deploy attacker VM: {e}[/red]")
        return False
    finally:
        conn.close()

def teardown_lab(vm_name: str) -> None:
    console.print(f"\n[bold yellow]Tearing down '{vm_name}'...[/bold yellow]\n")

    conn = get_connection()
    try:
        try:
            dom = conn.lookupByName(vm_name)
            if dom.isActive():
                console.print(f"[cyan]Powering off '{vm_name}'...[/cyan]")
                dom.destroy()
            dom.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA)
            console.print(f"[green]VM '{vm_name}' removed.[/green]")
        except libvirt.libvirtError:
            console.print(f"[dim]VM '{vm_name}' not found. Skipping.[/dim]")

        if network_has_other_vms(conn, NET_NAME, exclude_vm=vm_name):
            console.print(f"[yellow]Network '{NET_NAME}' still in use by other VMs. Leaving it active.[/yellow]")
        else:
            try:
                network = conn.networkLookupByName(NET_NAME)
                if network.isActive():
                    network.destroy()
                network.undefine()
                console.print(f"[green]Network '{NET_NAME}' removed.[/green]")
            except libvirt.libvirtError:
                console.print(f"[dim]Network '{NET_NAME}' not found. Skipping.[/dim]")

        instance_disk = IMAGES_DIR / f"{vm_name}_instance.qcow2"
        if instance_disk.exists():
            try:
                os.remove(instance_disk)
                console.print(f"[green]Instance disk deleted (base image preserved).[/green]")
            except PermissionError:
                console.print(f"[red]Permission denied deleting {instance_disk}. Check SELinux or run with appropriate privileges.[/red]")
        else:
            console.print(f"[dim]No instance disk found for '{vm_name}'.[/dim]")

    finally:
        conn.close()

    console.print("\n[bold green]Teardown complete.[/bold green]\n")
