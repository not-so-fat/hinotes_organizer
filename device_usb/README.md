# device_usb

Minimal HiDock USB protocol layer used by `scripts/sync_device.mjs`.

We vendor this code in-repo instead of depending on an external package. It covers only what the sync pipeline needs: connect, list files, download, delete, and storage info.

## Build

```bash
cd device_usb
npm install
npm run build
```

Requires **Node.js 22+** and **libusb** (`brew install libusb` on macOS).

## Provenance

Implementation derived from [hidock-mcp](https://github.com/kms254/hidock-mcp) (MIT, v1.0.1), with file download added for this project. The wire protocol matches HiDock's [public test interface](https://hw.test.hidock.com/).

See [docs/research-and-approach.md](../docs/research-and-approach.md) for other reference implementations (hidock-next, HiDockSkill).
