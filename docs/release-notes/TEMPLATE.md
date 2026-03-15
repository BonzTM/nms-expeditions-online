<!-- Copy this template to <version>.md when drafting a new release. -->
<!-- Delete any sections that don't apply. -->

Play any expired No Man's Sky expedition online with full multiplayer — see other players, visit the Anomaly, and play with friends.

Drop in your expedition JSON, run the tool, and launch the game. The local proxy intercepts NMS season data and patches the auth response so the game believes your chosen expedition is active. All other traffic (multiplayer, discovery services, bases) passes through untouched.

## Features

- Full multiplayer support — Steam P2P networking is unaffected; you'll see other players and can group up normally
- Automatic expedition loading — The proxy serves expedition data directly to the game with the correct hash and content type. No manual file placement into game directories needed.
- Ephemeral TLS certificates — CA and per-host certificates are generated in memory at runtime. Nothing left on disk.
- Validated upstream connections — All traffic forwarded to real NMS servers uses proper SSL certificate validation
- HTTP keep-alive — Handles multiple requests per connection
- Cross-platform — Windows (.exe with automatic UAC elevation) and Linux (./run.sh handles everything)
- Simple menu interface — Install hosts entries, start the proxy, uninstall when done

## Getting Started

1. Download your expedition from https://cwmonkey.github.io/nms-expeditions/
2. Place SEASON_DATA_CACHE.JSON next to the executable (Windows) or in the project directory (Linux)
3. Run the tool, install, start the proxy, launch NMS

See the README.md for detailed instructions.

---

## {VERSION}

## What's New

<!-- New features, capabilities, or user-facing additions. -->

-

## Changed

<!-- Modifications to existing behavior, refactors, or improvements. -->

-

## Security

<!-- Security fixes or hardening. Include CVE references if applicable. -->

-

## Fixed

<!-- Bug fixes. Reference issue numbers where possible. -->

-

## Technical Notes

<!-- Optional deeper context for contributors or advanced users. -->

**Full Changelog**: https://github.com/BonzTM/nms-expeditions-online/compare/PREVIOUS_TAG...NEW_TAG
