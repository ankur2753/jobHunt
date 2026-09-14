# Infrastructure and deployment guide

This document outlines how to deploy the job hunt agent to the cloud. Job platforms like LinkedIn and Naukri aggressively block datacenter IP addresses. We avoid these bans by routing traffic through a residential proxy tunnel. 

## System architecture

The setup splits compute power and network routing. 

An Oracle Cloud Always Free Tier instance provides the compute. It has 4 ARM64 cores and 24GB of RAM. It runs Docker, Playwright, the vector database, and the Telegram bot.

An old laptop or small device on your home network acts as the network exit. 

Tailscale connects the cloud server and the home device. The cloud server routes all outbound browser traffic through your home IP address. To the job platforms, the traffic looks like it comes from a residential connection.

## Set up the home exit node

1. Install a lightweight Linux distribution like Debian 32-bit or Alpine on an old device.
2. Connect it to your home Wi-Fi and disable sleep and suspend modes.
3. Install Tailscale by running `curl -fsSL https://tailscale.com/install.sh | sh`.
4. Authenticate your Tailscale account.
5. Advertise the device as an exit node with `sudo tailscale up --advertise-exit-node`.
6. Open your Tailscale admin console. Find the home device, edit the route settings, and approve it as an exit node.

## Set up the cloud server

1. Sign up for Oracle Cloud. Use a real credit card and turn off any VPNs during sign-up to avoid automated fraud bans.
2. Provision an Ampere A1 Compute instance running Ubuntu 22.04 or 24.04. Set it to 4 OCPUs and 24GB RAM.
3. SSH into the Oracle virtual machine from your main computer.
4. Install Docker and Docker Compose.
5. Install Tailscale by running `curl -fsSL https://tailscale.com/install.sh | sh`.
6. Route the Oracle server traffic through your home device with `sudo tailscale up --exit-node=<IP-of-home-node>`.

## Deploy and manage secrets

Do not commit your `.env` or `personal_details` folders to Git.

On the Oracle server, clone the repository:
```bash
git clone https://github.com/ankur2753/jobHunt.git /app/agent
cd /app/agent
```

On your local computer, copy your secrets to the cloud server using secure copy:
```bash
scp .env ubuntu@<Oracle-IP>:/app/agent/
scp -r personal_details/ ubuntu@<Oracle-IP>:/app/agent/
```

## Launch the agent

Start the containers on the Oracle server:
```bash
docker-compose up -d --build
```

Check the logs to verify the headless browser and database are running:
```bash
docker-compose logs -f
```

## Maintenance and debugging

You can verify the Oracle server is using your home IP address. Run `curl ifconfig.me` on the cloud server. It should return your home router's public IP address.

To update the code, SSH into the Oracle server, run `git pull`, and restart the service with `docker-compose restart job-hunt-agent`.

Your ChromaDB and browser cookies persist through Docker volumes. Back up the `vector_db/` and `personal_details/` folders to your local computer before terminating the Oracle server to avoid data loss.
