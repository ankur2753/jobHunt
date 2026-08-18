# Job Hunt Agent: Infrastructure & Deployment Guide

This document outlines the target architecture for deploying the Job Hunt Agent to the cloud while avoiding Datacenter IP bans (LinkedIn, Naukri) by using a residential proxy tunnel.

## The Architecture: "Cloud Muscle, Residential Face"

*   **Compute (The Muscle):** Oracle Cloud Always Free Tier (ARM64, 24GB RAM). Runs Docker, Playwright, Vector DB, and Telegram polling.
*   **Networking (The Face):** An old laptop (e.g., Acer Travelmate) or device sitting on your home Wi-Fi, acting as a Tailscale Exit Node.
*   **The Tunnel:** Tailscale (a free, zero-config WireGuard VPN) connects the two. Oracle routes all its outbound browser traffic through your home IP.

---

## Step-by-Step Implementation

### Phase 1: The Home Exit Node
1. Take your old hardware (e.g., the Acer laptop) and install a lightweight Linux distribution (Debian 32-bit or Alpine).
2. Connect it to your home Wi-Fi and ensure it stays awake (disable sleep/suspend).
3. Install Tailscale: `curl -fsSL https://tailscale.com/install.sh | sh`
4. Authenticate your Tailscale account.
5. Advertise the device as an exit node:
   ```bash
   sudo tailscale up --advertise-exit-node
   ```
6. Go to your [Tailscale Admin Console](https://login.tailscale.com/admin/machines), locate the Acer laptop, click "Edit route settings", and approve it as an Exit Node.

### Phase 2: The Oracle Cloud Setup
1. Sign up for Oracle Cloud (use a real credit card, disable VPNs during sign-up to avoid fraud flags).
2. Provision an **Ampere A1 Compute** instance (Ubuntu 22.04 or 24.04). Max out the free tier sliders: **4 OCPUs, 24GB RAM**.
3. SSH into your new Oracle VM from your main laptop.
4. Install Docker and Docker Compose.
5. Install Tailscale on the Oracle VM:
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   ```
6. Tell the Oracle VM to route its traffic through your home laptop:
   ```bash
   sudo tailscale up --exit-node=<IP-of-Acer-Tailscale-Node>
   ```

### Phase 3: Deployment & Secrets Management
*Never commit your `.env` or `personal_details` to Git.*

1. **On the Oracle Server:**
   ```bash
   git clone https://github.com/ankur2753/jobHunt.git /app/agent
   cd /app/agent
   ```
2. **On your Main Laptop (Local):** Securely copy your secrets to the server.
   ```bash
   # Copy environment variables
   scp .env ubuntu@<Oracle-IP>:/app/agent/

   # Copy persistent cookies/logins
   scp -r personal_details/ ubuntu@<Oracle-IP>:/app/agent/
   ```

### Phase 4: Launch
1. On the Oracle server, launch the agent:
   ```bash
   docker-compose up -d --build
   ```
2. Check the logs to ensure the headless browser and Redis are functioning:
   ```bash
   docker-compose logs -f
   ```

---

## Maintenance & Debugging
*   **Checking IP:** To verify Oracle is using your home IP, run `curl ifconfig.me` on the Oracle server while Tailscale is active. It should return your home router's public IP.
*   **Updating Code:** SSH into Oracle, `git pull`, and `docker-compose restart job-hunt-agent`.
*   **Database Persistence:** Your ChromaDB (`vector_db/`) and cookies (`personal_details/`) are mounted via Docker volumes. If you ever destroy the Oracle server, make sure to `scp` those folders back to your local laptop first to avoid losing data!
