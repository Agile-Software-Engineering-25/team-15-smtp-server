# SMTP Server

This repository contains all configs needed to deploy a SMTP server into the ASE k8s cluster.

# Setup

## DNS Setup

### jablonowski.dev

- A: 164.30.69.174
- MX: mail.jablonowski.dev
- TXT-Entries:
  1. `v=spf1 ip4:164.30.69.174 -all`
  2. `v=DMARC1; p=quarantine; rua=mailto:alexander.jablo@gmail.com`
     a;ex

### mail.jablonowski.dev

- A: 164.30.69.174

## DKIM Setup

1.  generate DKIM Keypair

```bash
opendkim-genkey -b 2048 -d jablonowski.dev -s mail
```

2. Create secret from `mail.private`. Add `-n <some-namespace>` if the secret should be in a specific namespace

```bash
kubectl create secret generic opendkim-key   --from-file=mail.private=./mail.private
```

3. add TXT Entry for jablonowski.dev

- prefix: mail.\_domainkey
  - so should be accessible on mail.\_domainkey.jablonowski.dev
- copy the context from `mail.txt` into the DNS TXT entry
  - not the whole content but everything inside the brackets formatted like this:

```
v=DKIM1; h=sha256; k=rsa; p=<some-public-key>
```

# TODO

- add [opendkim](http://www.opendkim.org/) and dkim entry to `jablonowski.dev`
- setup PTR (reverse DNS)
