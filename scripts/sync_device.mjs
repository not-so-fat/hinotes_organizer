#!/usr/bin/env node
/**
 * USB sync helper for HiDock P1.
 * Requires Chrome/HiNotes to be closed (exclusive USB access).
 *
 * Usage:
 *   node scripts/sync_device.mjs list [--include-wip]
 *   node scripts/sync_device.mjs download --name FILE.hda --out PATH [--length N]
 *   node scripts/sync_device.mjs delete --name FILE.hda
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { HiDockDevice } from "../device_usb/dist/device.js";

const REPO_ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const DEVICE_USB = path.join(REPO_ROOT, "device_usb", "dist", "device.js");

function parseArgs(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (token.startsWith("--")) {
      const key = token.slice(2);
      const next = argv[i + 1];
      if (next && !next.startsWith("--")) {
        args[key] = next;
        i++;
      } else {
        args[key] = true;
      }
    } else {
      args._.push(token);
    }
  }
  return args;
}

function shouldIncludeFile(name, includeWip) {
  if (!/\.hda$/i.test(name)) return false;
  if (includeWip) return true;
  return /-Rec\d+\.hda$/i.test(name);
}

function loadState(stateFile) {
  if (!fs.existsSync(stateFile)) return { files: {} };
  return JSON.parse(fs.readFileSync(stateFile, "utf8"));
}

function saveState(stateFile, state) {
  fs.mkdirSync(path.dirname(stateFile), { recursive: true });
  fs.writeFileSync(stateFile, JSON.stringify(state, null, 2) + "\n");
}

async function withDevice(fn) {
  const device = new HiDockDevice();
  try {
    await device.connect();
    return await fn(device);
  } finally {
    process.stderr.write("Closing USB connection...\n");
    await device.disconnect();
    process.stderr.write("USB connection closed.\n");
  }
}

async function cmdList(includeWip) {
  const result = await withDevice(async (device) => {
    const files = await device.listFiles();
    const filtered = (files ?? []).filter((f) => shouldIncludeFile(f.name, includeWip));
    return {
      device_model: device.deviceModel,
      count: filtered.length,
      files: filtered.map((f) => ({
        name: f.name,
        length: f.length,
        signature: f.signature,
        time: f.time ? f.time.toISOString() : null,
      })),
    };
  });
  console.log(JSON.stringify(result, null, 2));
}

async function cmdDownload(name, outPath, lengthArg) {
  await withDevice(async (device) => {
    let expectedLength = lengthArg ? Number(lengthArg) : null;
    if (!expectedLength) {
      const files = await device.listFiles();
      const match = (files ?? []).find((f) => f.name === name);
      if (!match) throw new Error(`File not found on device: ${name}`);
      expectedLength = match.length;
    }

    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    process.stderr.write(`Downloading ${name} (${expectedLength} bytes)...\n`);
    const data = await device.downloadFile(name, expectedLength, 900);
    fs.writeFileSync(outPath, data);
    process.stderr.write(`Saved ${outPath}\n`);
    console.log(
      JSON.stringify({
        name,
        out: outPath,
        bytes: data.length,
        signature_match: data.length === expectedLength,
      }),
    );
  });
}

async function cmdDelete(name) {
  await withDevice(async (device) => {
    const result = await device.deleteFile(name);
    const ok =
      result?.type === "deleteFile" && result.data?.result === "success";
    if (!ok) {
      const detail = result?.type === "deleteFile" ? result.data?.result : "unknown";
      throw new Error(`Failed to delete ${name}: ${detail}`);
    }
    process.stderr.write(`Deleted ${name} from device\n`);
    console.log(JSON.stringify({ deleted: name }));
  });
}

function formatMb(bytes) {
  return (bytes / 1024 / 1024).toFixed(1);
}

async function downloadWithProgress(device, file, audioPath) {
  let lastPct = -1;
  const started = Date.now();
  const data = await device.downloadFile(file.name, file.length, 900, (received, total) => {
    const pct = total > 0 ? Math.floor((received / total) * 100) : 0;
    if (pct >= lastPct + 5 || pct === 100) {
      lastPct = pct;
      const elapsed = ((Date.now() - started) / 1000).toFixed(0);
      process.stderr.write(
        `    ${formatMb(received)}/${formatMb(total)} MB (${pct}%) — ${elapsed}s elapsed\n`,
      );
    }
  });
  fs.mkdirSync(path.dirname(audioPath), { recursive: true });
  fs.writeFileSync(audioPath, data);
}

async function cmdSyncNew(cacheDir, stateFile, includeWip, limit) {
  const state = loadState(stateFile);
  const downloaded = [];

  await withDevice(async (device) => {
    process.stderr.write("Listing files on device...\n");
    const files = await device.listFiles();
    let pending = (files ?? []).filter((f) => {
      if (!shouldIncludeFile(f.name, includeWip)) return false;
      const rec = state.files?.[f.signature];
      if (rec?.audio_path && fs.existsSync(rec.audio_path)) return false;
      return true;
    });

    pending.sort((a, b) => {
      const ta = a.time ? a.time.getTime() : 0;
      const tb = b.time ? b.time.getTime() : 0;
      return tb - ta;
    });

    const totalPending = pending.length;
    if (limit) {
      pending = pending.slice(0, limit);
      process.stderr.write(
        `${totalPending} new on device → downloading ${pending.length} (limit ${limit}, newest first)\n`,
      );
    } else {
      process.stderr.write(`${pending.length} new file(s) to download\n`);
    }

    for (let i = 0; i < pending.length; i++) {
      const file = pending[i];
      const audioPath = path.join(cacheDir, file.name.replace(/\.hda$/i, ".mp3"));
      const sizeMb = formatMb(file.length);
      process.stderr.write(
        `[${i + 1}/${pending.length}] ${file.name} (${sizeMb} MB)\n`,
      );
      await downloadWithProgress(device, file, audioPath);
      process.stderr.write(`    saved ${audioPath}\n`);

      state.files = state.files || {};
      state.files[file.signature] = {
        ...(state.files[file.signature] || {}),
        signature: file.signature,
        device_file: file.name,
        recorded_at: file.time ? file.time.toISOString() : null,
        downloaded_at: new Date().toISOString(),
        audio_path: audioPath,
      };
      saveState(stateFile, state);
      downloaded.push({ name: file.name, signature: file.signature, audio_path: audioPath });
    }
    process.stderr.write("All downloads complete.\n");
  });

  process.stderr.write("Sync result ready.\n");
  console.log(JSON.stringify({
    downloaded_count: downloaded.length,
    limit: limit ?? null,
    downloaded,
  }, null, 2));
}

async function main() {
  if (!fs.existsSync(DEVICE_USB)) {
    console.error(
      "device_usb not built. Run: cd device_usb && npm install && npm run build",
    );
    process.exit(1);
  }

  const args = parseArgs(process.argv.slice(2));
  const command = args._[0];

  try {
    if (command === "list") {
      await cmdList(Boolean(args["include-wip"]));
      return;
    }
    if (command === "download") {
      const name = args.name;
      const out = args.out;
      if (!name || !out) {
        console.error("Usage: download --name FILE.hda --out PATH [--length N]");
        process.exit(1);
      }
      await cmdDownload(name, path.resolve(out), args.length);
      return;
    }
    if (command === "delete") {
      const name = args.name;
      if (!name) {
        console.error("Usage: delete --name FILE.hda");
        process.exit(1);
      }
      await cmdDelete(name);
      return;
    }
    if (command === "sync-new") {
      const cacheDir = path.resolve(args["cache-dir"] || ".cache/audio");
      const stateFile = path.resolve(args["state-file"] || ".state/pipeline.json");
      await cmdSyncNew(cacheDir, stateFile, Boolean(args["include-wip"]), args.limit ? Number(args.limit) : null);
      return;
    }

    console.error(`Unknown command: ${command ?? "(none)"}`);
    console.error("Commands: list | download | delete | sync-new");
    process.exit(1);
  } catch (err) {
    console.error(JSON.stringify({ error: err.message ?? String(err) }));
    process.exit(1);
  }
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error(JSON.stringify({ error: err.message ?? String(err) }));
    process.exit(1);
  });
