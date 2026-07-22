# Continuous integration

Pull requests run Bambu's canonical `scripts/check.sh` gate on Linux through the SHA-pinned
`njrun1804-cc/engineering-control-plane` profile. The shared workflow validates the strict
`check_receipt.v2` receipt and has read-only repository permissions.

CI never contacts a printer, starts a print, or treats slicing output as physical proof.
