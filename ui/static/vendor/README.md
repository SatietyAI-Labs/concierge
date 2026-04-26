# Vendored frontend assets

Concierge's UI vendors HTMX and Pico.css under this directory rather than loading them from a CDN. The rationale is **offline-friendly + reproducible-build**: a fresh clone of the repository can run the dashboard with no third-party network dependency at runtime, and the exact bytes shipped in the repo are reproducible from the recorded version pins and SHA256 hashes below.

## Vendored assets

### HTMX

- **File:** `htmx.min.js`
- **Version:** 2.0.10
- **Source:** https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js
- **SHA256:** `71ea67185bfa8c98c39d31717c6fce5d852370fcdfd129db4543774d3145c0de`
- **License:** BSD-2-Clause (compatible with MIT)
- **Upstream:** https://github.com/bigskysoftware/htmx

### Pico.css

- **File:** `pico.min.css`
- **Version:** 2.1.1
- **Source:** https://unpkg.com/@picocss/pico@2.1.1/css/pico.min.css
- **SHA256:** `fbc9a63fc9fc9f72d12fd7fc9806e11fa9f77ae4f9cad146b27003a1119ba3db`
- **License:** MIT (compatible with MIT)
- **Upstream:** https://github.com/picocss/pico

## Verifying the vendored bytes

```bash
sha256sum ui/static/vendor/htmx.min.js ui/static/vendor/pico.min.css
```

Expected output matches the SHA256 hashes recorded above.

## Updating

To bump versions: download fresh files from the recorded source URLs (substituting the new version), record the new SHA256 hashes here, and commit both the binary update and this README update in the same commit. Treat the README as the canonical version-pin record.
