# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please do not open a public issue for security problems. Report them privately through
[GitHub Security Advisories](https://github.com/burhan-mujahid/repo2video/security/advisories/new).
You can expect an acknowledgement within three working days and a status update within ten.

## Scope

repo2video reads repositories you point it at and renders them in a local headless browser. Areas of particular
interest are:

- content from an analyzed repository being executed rather than displayed (script injection into the render page);
- path traversal when reading repository files or writing output folders;
- the remote downloads the tool performs (the voice model from GitHub Releases).
