# Setup: lemon.berkeley.mt (DNS) and Google sign-in for /super

Two one-time jobs, in this order. Prod today: `https://52-33-41-153.sslip.io` on one EC2 instance.

## 1. DNS: lemon.berkeley.mt

**What to send the BMT technical lead** (whoever manages `berkeley.mt` DNS):

| Type | Name | Value | TTL |
|---|---|---|---|
| `A` | `lemon` (that is `lemon.berkeley.mt`) | `52.33.41.153` | 300 |

No `AAAA` and no `CNAME`. If the DNS is on Cloudflare, set the record to **DNS only** (grey cloud), not proxied, so Caddy can get its certificate.

**Where the IP comes from.** The `sslip.io` name is the IP with dashes: `52-33-41-153` is `52.33.41.153`. To confirm in AWS: Console → EC2 → Instances → select the instance → **Public IPv4 address** (not the "Public IPv4 DNS", not the private IP).

**Make sure that IP never changes.** A normal public IP changes when the instance is stopped and started. In EC2 → Network & Security → **Elastic IPs**: if `52.33.41.153` is listed and associated with the instance, you're done. If not: *Allocate Elastic IP address* → select it → *Actions → Associate Elastic IP address* → pick the instance. That gives a (possibly new) fixed IP, so use *that* number in the record, and the sslip URL changes with it. An Elastic IP is free while it is attached to a running instance. Do this **before** sending the record.

**Security group.** The instance already serves HTTPS, so ports 80 and 443 are open. Keep both: Caddy needs 80/443 to get the certificate.

**When the record is live** (check: `dig +short lemon.berkeley.mt` prints `52.33.41.153`, or use dnschecker.org), on the server:

```bash
sudo su - ubuntu
nano ~/proctor-suite/infra/.env        # SITE_ADDRESS=lemon.berkeley.mt
cd ~/proctor-suite/infra && bash deploy.sh
```

Caddy gets a Let's Encrypt certificate by itself (first start takes about a minute). Then open `https://lemon.berkeley.mt/healthz` (`ok`). The old sslip address stops working, and everyone signs in again (cookies belong to the host name). Also add the new origin in Google (below).

## 2. Google sign-in for the super-admin page

The page uses the Google "Sign in with Google" button. Google gives the browser a signed token, the server checks it and then checks the email against the super-admin list. We only need a **Client ID**, no client secret, no redirect URL.

1. Go to <https://console.cloud.google.com>, sign in, and create a project (top bar → project picker → *New project*, name it Lemon). If `berkeley.mt` is a Google Workspace, create it under that organization.
2. Open **APIs & Services → OAuth consent screen** (new UI: **Google Auth Platform**) and *Get started*:
   - App name: the site name. User support email: yours. Developer contact: yours.
   - Audience: **Internal** if the project is under a `berkeley.mt` Workspace organization and every super-admin has a `berkeley.mt` account. Otherwise **External**.
   - Under *Branding* you can add the logo and the authorized domain `berkeley.mt`.
   - If you chose External, the publishing status starts as *Testing*: only listed test users can sign in. Either add every super-admin email under **Audience → Test users**, or press **Publish app** (we only ask for basic email and profile, so no Google review is needed).
3. Open **Clients** (old UI: **Credentials → Create credentials → OAuth client ID**):
   - Application type: **Web application**. Name: Lemon.
   - **Authorized JavaScript origins** (add each; no path, no trailing slash):
     - `https://lemon.berkeley.mt`
     - `https://52-33-41-153.sslip.io` (the current address; if Google refuses it, skip it and test on the real domain)
     - `https://localhost` and `http://localhost` (to try it with `docker compose` on your laptop)
   - **Authorized redirect URIs**: leave empty.
   - *Create*, then copy the **Client ID** (ends in `.apps.googleusercontent.com`).
4. On the server, in `infra/.env`:
   ```
   GOOGLE_CLIENT_ID=1234567890-abc....apps.googleusercontent.com
   SUPER_ADMIN_EMAILS=you@berkeley.edu
   ```
   `SUPER_ADMIN_EMAILS` is the bootstrap list (comma-separated). Those emails can always sign in and cannot be removed on the page. Everyone else is added on the page itself. Then `bash deploy.sh`.
5. Open `https://<your address>/super` and sign in. Origin changes in Google can take a few minutes (sometimes longer) to apply.

If the button says "Not a valid origin" or "origin_mismatch", the address in the browser isn't on the origins list exactly (scheme, host, port).
