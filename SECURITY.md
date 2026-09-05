# Security policy

## Supported version

Security fixes are applied to the current `main` branch and the public deployment built from it. Historical commits and locally modified copies are not supported releases.

## Reporting a vulnerability

Do not open a public issue for a vulnerability, exposed secret or report containing exploit details. Email `mail@projectfiner.com` with the subject `Project FINER security report`.

Please include:

- the affected URL, file or component;
- the impact and conditions required to reproduce it;
- concise reproduction steps or a proof of concept;
- any evidence that data or credentials were exposed;
- a safe way to contact you.

Avoid accessing, changing or retaining data beyond what is necessary to demonstrate the issue. Do not degrade the service, run denial-of-service tests, use social engineering or publish an unresolved report without coordination.

Project FINER does not currently operate a bug-bounty programme and cannot promise payment. Receipt will be acknowledged when operationally possible; validation, remediation and disclosure timing depend on severity and maintainer capacity.

## Scope notes

The static site, repository code and Project FINER API are in scope. Vulnerabilities solely in an upstream publisher or unrelated third-party service should be reported to that provider. Data-quality corrections are handled under [`CORRECTIONS.md`](CORRECTIONS.md), not this security process.

## Deployment protections

Every published HTML page carries a Content Security Policy and a strict-origin referrer policy. Plotly is copied from the locked npm dependency tree at build time; the remaining Leaflet CDN files are version-pinned and protected by Subresource Integrity.

These document-level controls do not replace HTTP response headers. The GitHub Pages origin cannot configure repository-defined HSTS, `X-Content-Type-Options`, `Permissions-Policy` or CSP `frame-ancestors`. Those controls must be configured and verified at the Cloudflare edge for `projectfiner.com`.
