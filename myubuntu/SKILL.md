---
name: myubuntu
description: Safely inspect, maintain, troubleshoot, or extend the MyUbuntu personal Ubuntu server using its established directory layout, Docker Compose service locations, ports, persistence rules, and remote-access constraints. Use for MyUbuntu server operations; do not use as generic Ubuntu guidance for unrelated hosts.
---

# MyUbuntu

Operate the user's personal Ubuntu server consistently and conservatively.

## Start here

1. Read [references/server-profile.md](references/server-profile.md) when the task depends on host addresses, ports, directories, service inventory, container names, or recorded versions.
2. Read [references/operations.md](references/operations.md) before changing a service, diagnosing it, backing it up, upgrading it, or giving commands that affect availability or persisted data.
3. Treat recorded versions, health, exposure, and configuration as a dated snapshot. Inspect the live server before relying on them for a change.

## Operating rules

- Keep system configuration in `/etc`, deployed applications in `/opt/apps`, middleware in `/opt/middleware`, runtimes in `/opt/runtime`, manually installed tools in `/opt/tools`, persistent data in `/data`, application logs in `/var/log/apps`, and static sites in `/var/www`.
- Keep each Compose-managed service self-contained with `docker-compose.yml`, `conf/`, and `scripts/` where applicable. Put persistent state on the host under `/data`; do not rely on container filesystems for important data.
- Prefer inspection before mutation. Identify the actual host, current working directory, Compose file, container state, mounted data directories, and available recovery path.
- Distinguish start, stop, restart, inspection, container removal, data deletion, backup, restore, and upgrade. Never present them as interchangeable.
- For remote-network changes, determine whether the active session depends on the component being changed. Require a tested alternative access path before restarting, disconnecting, upgrading, or logging out Tailscale or changing SSH/network configuration.
- Before destructive or hard-to-reverse actions, show the exact target and impact and obtain explicit user confirmation. This includes deleting persistent directories, restoring backups, pruning Docker data, replacing configuration, or changing authentication/network exposure.
- Never invent, repeat, store, or request credentials in chat when a safer interactive or secret-manager flow is available. The source document contained credentials; they are intentionally excluded from this skill. Use placeholders such as `<password>` and `<auth-key>`.
- Bind administrative web interfaces only to trusted addresses where practical. Do not expose Jenkins, RocketMQ Dashboard, SkyWalking UI, Nacos, Cockpit, databases, or other administration endpoints to the public internet without authentication, HTTPS, firewall rules, and a clear user request.
- When drafting new configuration, preserve the established names and locations unless the user asks to migrate them. Validate syntax and health after a change, and report what was actually verified.

## Response shape

For an operational task, state prerequisites and impact, provide the smallest safe command sequence, then give verification and rollback/recovery guidance. Mark host-specific examples clearly and use placeholders for all secrets.
