"""
CLI application for Tailscale Network Monitor.
"""
import typer
import sys
import os
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich import box
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
import time
from datetime import datetime
import subprocess

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.constants import CLI_NAME, CLI_VERSION

app = typer.Typer(
    name=CLI_NAME,
    help="Tailscale Network Traffic Monitor CLI",
    add_completion=False
)
console = Console()


def get_collector_url() -> str:
    """Get collector URL from environment or default."""
    default_url = os.getenv("COLLECTOR_URL")
    if not default_url:
        # Try to get Tailscale IP
        try:
            import subprocess
            result = subprocess.run(
                ["ip", "-4", "addr", "show", "tailscale0"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                import re
                match = re.search(r'inet (\d+\.\d+\.\d+\.\d+)', result.stdout)
                if match:
                    default_url = f"http://{match.group(1)}:8080"
        except:
            pass
    return default_url or "http://localhost:8080"


def check_collector_running() -> bool:
    """Check if collector service is running."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "tailscale-monitor-collector"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


@app.command()
def agents():
    """List all registered agents with their status."""
    import requests
    
    collector_url = get_collector_url()
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Fetching agents...", total=None)
            response = requests.get(f"{collector_url}/api/v1/agents", timeout=5)
            progress.update(task, completed=True)
        
        response.raise_for_status()
        agents_data = response.json()
        
        if not agents_data:
            console.print("[yellow]No agents registered yet.[/yellow]")
            return
        
        # Create table
        table = Table(title="📡 Registered Agents", box=box.ROUNDED)
        table.add_column("Hostname", style="cyan", no_wrap=True)
        table.add_column("Tailscale IP", style="blue")
        table.add_column("OS", style="magenta")
        table.add_column("Status", style="bold")
        table.add_column("Last Seen", style="dim")
        
        for agent in agents_data:
            status_color = "green" if agent["status"] == "online" else "red"
            status_icon = "●" if agent["status"] == "online" else "○"
            
            # Format last seen
            last_seen = datetime.fromisoformat(agent["last_seen"].replace('Z', '+00:00'))
            time_diff = datetime.now(last_seen.tzinfo) - last_seen
            
            if time_diff.seconds < 60:
                last_seen_str = "Just now"
            elif time_diff.seconds < 3600:
                last_seen_str = f"{time_diff.seconds // 60}m ago"
            elif time_diff.days == 0:
                last_seen_str = f"{time_diff.seconds // 3600}h ago"
            else:
                last_seen_str = f"{time_diff.days}d ago"
            
            table.add_row(
                agent["hostname"],
                agent["tailscale_ip"],
                agent["os_type"],
                f"[{status_color}]{status_icon} {agent['status']}[/{status_color}]",
                last_seen_str
            )
        
        console.print(table)
        console.print(f"\n[dim]Total: {len(agents_data)} agents[/dim]")
    
    except requests.exceptions.ConnectionError:
        console.print("[red]Error: Cannot connect to collector.[/red]")
        console.print(f"[dim]Collector URL: {collector_url}[/dim]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def dashboard(refresh: int = typer.Option(5, help="Refresh interval in seconds")):
    """Show live dashboard with network statistics."""
    import requests
    
    collector_url = get_collector_url()
    
    def generate_dashboard():
        """Generate dashboard layout."""
        try:
            response = requests.get(f"{collector_url}/api/v1/traffic/summary", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            layout = Layout()
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="body"),
                Layout(name="footer", size=3)
            )
            
            # Header
            summary = data["summary"]
            header_text = (
                f"[bold cyan]Tailscale Network Monitor[/bold cyan] | "
                f"Hosts: {summary['online_hosts']}/{summary['total_hosts']} online | "
                f"Traffic: {summary['total_traffic_gb']:.2f} GB | "
                f"Avg: {summary['avg_bandwidth_mbps']:.2f} Mbps"
            )
            layout["header"].update(Panel(header_text, border_style="cyan"))
            
            # Body - Hosts table
            hosts_table = Table(box=box.SIMPLE)
            hosts_table.add_column("Hostname", style="cyan")
            hosts_table.add_column("IP", style="blue")
            hosts_table.add_column("Status", style="bold")
            hosts_table.add_column("↑ Upload", justify="right", style="green")
            hosts_table.add_column("↓ Download", justify="right", style="yellow")
            hosts_table.add_column("Sent", justify="right", style="dim")
            hosts_table.add_column("Received", justify="right", style="dim")
            
            for host in data["hosts"]:
                status_color = "green" if host["status"] == "online" else "red"
                status_icon = "●" if host["status"] == "online" else "○"
                
                hosts_table.add_row(
                    host["hostname"],
                    host["ip"],
                    f"[{status_color}]{status_icon}[/{status_color}]",
                    f"{host['traffic']['current_upload']:.2f} Mbps",
                    f"{host['traffic']['current_download']:.2f} Mbps",
                    f"{host['traffic']['sent_gb']:.2f} GB",
                    f"{host['traffic']['received_gb']:.2f} GB"
                )
            
            layout["body"].update(Panel(hosts_table, title="📊 Host Statistics", border_style="blue"))
            
            # Footer
            update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            footer_text = f"[dim]Last updated: {update_time} | Press Ctrl+C to exit[/dim]"
            layout["footer"].update(Panel(footer_text, border_style="dim"))
            
            return layout
        
        except requests.exceptions.ConnectionError:
            return Panel(
                "[red]Cannot connect to collector[/red]\n"
                f"[dim]URL: {collector_url}[/dim]",
                title="Error",
                border_style="red"
            )
        except Exception as e:
            return Panel(f"[red]Error: {e}[/red]", title="Error", border_style="red")
    
    console.print("[cyan]Starting dashboard... Press Ctrl+C to exit[/cyan]\n")
    
    try:
        with Live(generate_dashboard(), refresh_per_second=1/refresh, console=console) as live:
            while True:
                time.sleep(refresh)
                live.update(generate_dashboard())
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")


@app.command()
def generate_install():
    """Generate installation command for a new agent."""
    console.print(Panel.fit(
        "[bold cyan]Agent Installation Generator[/bold cyan]",
        border_style="cyan"
    ))
    
    # Ask for OS type
    console.print("\n[bold]Select target operating system:[/bold]")
    console.print("  [1] Linux (Debian/Ubuntu/RHEL/etc.)")
    console.print("  [2] Windows")
    
    os_choice = Prompt.ask("\nChoice", choices=["1", "2"], default="1")
    
    os_type = "linux" if os_choice == "1" else "windows"
    collector_url = get_collector_url()
    
    console.print(f"\n[green]✓[/green] Selected: [cyan]{os_type.capitalize()}[/cyan]")
    
    # Show installation command
    console.print("\n[bold]Installation Command:[/bold]\n")
    
    if os_type == "linux":
        install_cmd = (
            f"COLLECTOR_URL={collector_url} curl -fsSL {collector_url}/install/agent.sh | "
            f"sudo bash"
        )
        
        console.print(Panel(
            install_cmd,
            title="Linux Installation",
            border_style="green",
            padding=(1, 2)
        ))
        
        console.print("\n[dim]On the target Linux machine, run:[/dim]")
        console.print(f"  {install_cmd}\n")
    else:
        install_cmd = (
            f"$env:COLLECTOR_URL='{collector_url}'; "
            f"iwr -useb {collector_url}/install/agent.ps1 | iex"
        )
        
        console.print(Panel(
            install_cmd,
            title="Windows Installation (PowerShell as Administrator)",
            border_style="blue",
            padding=(1, 2)
        ))
        
        console.print("\n[dim]On the target Windows machine, run in PowerShell (as Admin):[/dim]")
        console.print(f"  {install_cmd}\n")
    
    console.print("[yellow]Note:[/yellow] The agent will automatically register with the collector on first run.")


@app.command()
def server(
    action: str = typer.Argument(..., help="Action: start, stop, restart, status, logs")
):
    """Manage the collector server service."""
    service_name = "tailscale-monitor-collector"
    
    valid_actions = ["start", "stop", "restart", "status", "logs"]
    if action not in valid_actions:
        console.print(f"[red]Error: Invalid action '{action}'[/red]")
        console.print(f"[dim]Valid actions: {', '.join(valid_actions)}[/dim]")
        return
    
    try:
        if action == "logs":
            # Show logs
            console.print(f"[cyan]Showing logs for {service_name}...[/cyan]\n")
            subprocess.run(["journalctl", "-u", service_name, "-f"])
        else:
            # Systemctl command
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task(f"{action.capitalize()}ing service...", total=None)
                
                result = subprocess.run(
                    ["sudo", "systemctl", action, service_name],
                    capture_output=True,
                    text=True
                )
                
                progress.update(task, completed=True)
            
            if result.returncode == 0:
                console.print(f"[green]✓[/green] Service {action}ed successfully")
                
                # Show status
                if action != "status":
                    time.sleep(1)
                    status_result = subprocess.run(
                        ["systemctl", "is-active", service_name],
                        capture_output=True,
                        text=True
                    )
                    status = status_result.stdout.strip()
                    status_color = "green" if status == "active" else "red"
                    console.print(f"Status: [{status_color}]{status}[/{status_color}]")
            else:
                console.print(f"[red]Error: {result.stderr}[/red]")
    
    except FileNotFoundError:
        console.print("[red]Error: systemctl not found. Are you on a systemd-based system?[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@app.command()
def version():
    """Show version information."""
    console.print(Panel.fit(
        f"[bold cyan]{CLI_NAME}[/bold cyan] v{CLI_VERSION}\n"
        f"Tailscale Network Traffic Monitor",
        border_style="cyan"
    ))


if __name__ == "__main__":
    app()
