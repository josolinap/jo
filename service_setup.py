#!/usr/bin/env python3
"""
Service Setup for Ouroboros
Configures Ouroboros to start automatically on boot.
"""

import subprocess
import sys
from pathlib import Path

def setup_systemd_service():
    """Setup systemd service for automatic startup."""
    service_content = """[Unit]
Description=Ouroboros AI Agent
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/jo-project
ExecStart=/usr/bin/python3 /root/jo-project/start_ouroboros.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

[Install]
WantedBy=multi-user.target
"""
    
    service_file = Path("/etc/systemd/system/ouroboros.service")
    service_file.write_text(service_content)
    
    print("Service file created at:", service_file)
    
    # Reload systemd
    subprocess.run(["systemctl", "daemon-reload"], check=False)
    
    # Enable service
    subprocess.run(["systemctl", "enable", "ouroboros"], check=False)
    
    print("✅ Ouroboros service installed")
    print("   Start with: systemctl start ouroboros")
    print("   Stop with: systemctl stop ouroboros")
    print("   Status: systemctl status ouroboros")
    print("   Logs: journalctl -u ouroboros -f")


def setup_cron_job():
    """Setup cron job for automatic startup."""
    cron_job = "@reboot cd /root/jo-project && /usr/bin/python3 start_ouroboros.py >> /tmp/ouroboros_cron.log 2>&1"
    
    # Add to crontab
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True
    )
    
    current_crontab = result.stdout
    if cron_job not in current_crontab:
        new_crontab = current_crontab + "\n" + cron_job + "\n"
        subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            text=True
        )
        print("✅ Cron job added for automatic startup")
    else:
        print("✅ Cron job already exists")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "cron":
        setup_cron_job()
    else:
        setup_systemd_service()