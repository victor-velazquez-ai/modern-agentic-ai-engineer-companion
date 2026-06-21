# VPN Access and Setup

The company VPN is required whenever you access internal systems from outside the office
network. Install the VPN client from the IT self-service portal. Sign in with your company SSO
credentials and approve the MFA prompt to connect.

If the VPN fails to connect, first confirm you are not already on the office network (the VPN
will refuse to connect on-site). Next, restart the VPN client. If it still fails, check the IT
status page for a known outage before opening a ticket.

Split tunneling is disabled by policy: while connected, all of your traffic routes through the
company network. This is intentional and protects Restricted data in transit. Do not attempt to
bypass it.

For persistent VPN problems, open a ticket with IT and include the error code shown in the
client and your operating system version.
