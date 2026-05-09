import asyncio
import concurrent.futures
import socket
import subprocess

import psutil
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from bot.handlers.core import is_authorized


async def netstat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return

    def _collect():
        rows: dict[str, list[str]] = {}
        for conn in psutil.net_connections(kind='inet'):
            if conn.status not in ('ESTABLISHED', 'LISTEN'):
                continue
            try:
                name = psutil.Process(conn.pid).name() if conn.pid else 'system'
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                name = f'pid:{conn.pid}'
            raddr = conn.raddr
            if not raddr:
                continue
            try:
                host = socket.gethostbyaddr(raddr.ip)[0]
            except socket.herror:
                host = raddr.ip
            rows.setdefault(name, []).append(host)
        return rows

    rows = await asyncio.to_thread(_collect)
    if not rows:
        await update.message.reply_text("No active connections.")
        return

    lines = ["🌐 <b>Active Connections</b>", ""]
    for proc, hosts in sorted(rows.items())[:20]:
        unique = list(dict.fromkeys(hosts))[:4]
        lines.append(f"<b>{proc}</b> → {', '.join(unique)}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def lan_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    msg = await update.message.reply_text("📡 Scanning LAN… (~5s)")

    def _scan():
        # Determine local subnet
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        finally:
            s.close()
        subnet = '.'.join(local_ip.split('.')[:3])

        # Ping sweep to populate ARP table
        def _ping(ip):
            subprocess.run(
                ['ping', '-n', '1', '-w', '150', ip],
                capture_output=True
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as ex:
            list(ex.map(_ping, [f"{subnet}.{i}" for i in range(1, 255)]))

        # Read ARP table
        arp = subprocess.run(['arp', '-a'], capture_output=True, text=True)
        devices = []
        for line in arp.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].count('.') == 3:
                ip, mac = parts[0], parts[1]
                if mac in ('ff-ff-ff-ff-ff-ff', 'ff:ff:ff:ff:ff:ff'):
                    continue
                try:
                    hostname = socket.gethostbyaddr(ip)[0]
                except socket.herror:
                    hostname = ""
                if ip.startswith(subnet):
                    devices.append((ip, mac, hostname))
        devices.sort(key=lambda x: [int(p) for p in x[0].split('.')])
        return devices, local_ip

    devices, local_ip = await asyncio.to_thread(_scan)

    lines = [f"📡 <b>LAN Devices</b>  (this PC: {local_ip})", ""]
    for ip, mac, hostname in devices:
        label = f" <i>{hostname}</i>" if hostname else ""
        lines.append(f"<code>{ip}</code>  {mac}{label}")

    if not devices:
        lines.append("No devices found.")

    await msg.edit_text("\n".join(lines), parse_mode=ParseMode.HTML)


def register_network_handlers(app) -> None:
    app.add_handler(CommandHandler("netstat",         netstat))
    app.add_handler(CommandHandler("whosonmynetwork", lan_scan))
    app.add_handler(CommandHandler("lan",             lan_scan))
