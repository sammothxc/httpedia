# Security Policy

## Supported Versions

HTTPedia is developed as a rolling release. Security fixes are applied to the
latest commit on the `main` branch and the most recent published Docker image.
Older commits and image tags are not maintained.

| Version            | Supported          |
| ------------------ | ------------------ |
| `main` (latest)    | :white_check_mark: |
| Older commits/tags | :x:                |

## Reporting a Vulnerability

Please **do not** report security vulnerabilities through public GitHub issues,
pull requests, or discussions.

Instead, report them privately through GitHub's built-in vulnerability reporting:

1. Go to the [Security tab](https://github.com/sammothxc/httpedia/security) of this repository.
2. Click **Report a vulnerability**.
3. Fill out the advisory form with as much detail as you can.

Please include, where possible:

- The type of issue (e.g. XSS, SSRF, path traversal, denial of service).
- The affected endpoint, file, or component.
- Steps to reproduce, including any proof-of-concept requests or payloads.
- The potential impact of the issue.

## What to Expect

- We aim to acknowledge new reports within **7 days**.
- We will keep you updated as we investigate and work on a fix.
- Once a fix is deployed, we're happy to credit you in the advisory unless you
  prefer to remain anonymous.

## Scope

HTTPedia is a lightweight, read-only proxy that fetches and reformats public
Wikipedia content. Reports that are especially relevant include:

- Cross-site scripting (XSS) in proxied or reflected content.
- Server-side request forgery (SSRF) or path traversal via article/image paths.
- Bypasses of the input validation or rate limiting.
- Anything that could compromise the host server.

The following are generally **out of scope**:

- Issues in Wikipedia's own content or upstream services.
- Missing HTTPS/TLS — serving over plain HTTP is intentional, to support
  vintage browsers that cannot negotiate modern TLS.
- Rate-limit thresholds being "too high" without a demonstrated impact.

Thank you for helping keep HTTPedia and its users safe.
