# Security Policy

## What This Tool Does

This tool uses techniques that security software may flag. This is by design — please read the [Security Transparency](README.md#security-transparency-windows) section in the README for a full explanation of:

- Why the `.exe` is unsigned and triggers SmartScreen warnings
- Why a CA certificate is installed in the Windows trust store (and why the risk is minimal)
- Why the hosts file is modified to redirect NMS API traffic
- Why administrator/root privileges are required

## Reporting a Vulnerability

If you discover a security vulnerability in this tool, please report it responsibly:

1. **Do not** open a public GitHub issue
2. Email the maintainer directly or use [GitHub's private vulnerability reporting](https://github.com/BonzTM/nms-expeditions-online/security/advisories/new)
3. Include a description of the vulnerability and steps to reproduce it
4. Allow reasonable time for a fix before public disclosure

## Scope

The following are considered security concerns for this project:

- CA private key being written to disk or persisted beyond a session
- Certificate validity windows that are unnecessarily long
- Hosts file entries not being properly cleaned up
- Traffic from non-NMS applications being intercepted or modified
- Privilege escalation beyond what is documented

The following are **not** security concerns (they are intentional design decisions):

- The tool installs a temporary CA certificate (documented, auto-removed, 48-hour expiry)
- The tool modifies the hosts file (documented, reversible)
- The tool requires administrator/root privileges (documented, necessary for hosts file and port 443)
- Antivirus software flagging the tool (expected behavior, documented)
