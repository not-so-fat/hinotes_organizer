// ─── Device Models ───────────────────────────────────────────────────────────

export type HiDockModel = "hidock-h1" | "hidock-h1e" | "hidock-p1" | "hidock-p1:mini" | "unknown";

export const ProductIdToModel: Record<number, HiDockModel> = {
  0xb00c: "hidock-h1",
  0xb00d: "hidock-h1e",
  0xb00e: "hidock-p1",
  0xb00f: "hidock-p1:mini",
};

export const VENDOR_ID = 0x10d6;

// ─── Command IDs (host → device) ────────────────────────────────────────────

export enum CommandId {
  QueryDeviceInfo = 0x01,
  QueryDeviceTime = 0x02,
  SetDeviceTime = 0x03,
  QueryFileList = 0x04,
  TransferFile = 0x05,
  QueryFileCount = 0x06,
  DeleteFile = 0x07,
  RequestFirmwareUpgrade = 0x08,
  FirmwareUpload = 0x09,
  BncDemoTest = 0x0a,
  GetSettings = 0x0b,
  SetSettings = 0x0c,
  GetFileBlock = 0x0d,
  ReadCardInfo = 0x10,
  FormatCard = 0x11,
  GetRecordingFile = 0x12,
  RequestUacUpdate = 0x18,
  UacUpdate = 0x19,
  MassStorage = 0xf00f,
  TestFirmwareVersion = 0xf001,
}

// ─── Wire Protocol ───────────────────────────────────────────────────────────

/** Two magic bytes that begin every frame: 0x12 0x34 */
export const FRAME_HEADER = [0x12, 0x34] as const;

/**
 * Binary frame layout (big-endian):
 *   [0..1]  header     – 0x12 0x34
 *   [2..3]  commandId  – uint16
 *   [4..7]  sequence   – uint32
 *   [8..11] length     – upper byte = padding count, lower 3 bytes = body length
 *   [12..]  body       – `length` bytes, followed by `padding` zero bytes
 */
export interface WireFrame {
  commandId: number;
  sequence: number;
  bodyLength: number;
  padding: number;
  body: number[];
}

// ─── Response Payloads ───────────────────────────────────────────────────────

export interface DeviceInfo {
  versionCode: string;
  versionNumber: number;
  sn: string;
}

export interface VersionInfo {
  bluetooth: string;
  dsp: string;
  uac: string;
  /** Inter-chip gateway downstream, hex string */
  igd: string;
  /** Inter-chip gateway upstream, hex string */
  igu: string;
  earphone: string;
  base: string;
}

export interface DeviceTime {
  /** Formatted as "YYYY-MM-DD HH:MM:SS" or "unknown" */
  time: string;
}

export interface FileInfo {
  name: string;
  /** Parsed recording timestamp, or null if filename doesn't match known patterns */
  time: Date | null;
  /** File size in bytes */
  length: number;
  /** File format version byte */
  version: number;
  /** MD5 hex signature (32 chars) */
  signature: string;
}

export interface FileCount {
  count: number;
}

export interface CardInfo {
  /** Used space in megabytes */
  used: number;
  /** Total capacity in megabytes */
  capacity: number;
  /** Status code as hex string */
  status: string;
}

export interface DeviceSettings {
  autoRecord: boolean;
  autoPlay: boolean;
  notification: boolean;
}

export interface CommandResult {
  result: "success" | "failed";
}

export interface DeleteFileResult {
  result: "success" | "not-exists" | "failed";
}

export interface FirmwareUpgradeResult {
  result: "accepted" | "wrong-version" | "busy" | "unknown";
}

export interface UacUpdateResult {
  code: number;
  result: "success" | "length-mismatch" | "busy" | "card-full" | "card-error" | string;
}

// ─── Settings Bitmask ────────────────────────────────────────────────────────

/**
 * Settings are sent as a 12-byte array.
 * Byte indices: [3] = autoRecord, [7] = autoPlay, [11] = notification
 * Values: 0 = unchanged, 1 = enable, 2 = disable
 */
export interface SetSettingsPayload {
  autoRecord?: boolean;
  autoPlay?: boolean;
  notification?: boolean;
}

// ─── UAC Firmware Catalog ────────────────────────────────────────────────────

export interface UacFirmware {
  url: string;
  md5: string;
}

export const UAC_FIRMWARES: Partial<Record<HiDockModel, UacFirmware>> = {
  "hidock-h1": { url: "/raw/jensen-1-uac.bin", md5: "92e66fd8cfd36f09c83fc61491899307" },
  "hidock-h1e": { url: "/raw/jensen-3-uac.bin", md5: "c355c5bf8cc8a8da8bea6b6315ad7649" },
};

// ─── USB Transport Constants ─────────────────────────────────────────────────

export const USB_CONFIGURATION = 1;
export const USB_INTERFACE = 0;
export const USB_ALT_INTERFACE = 0;
export const USB_ENDPOINT_IN = 2;
export const USB_ENDPOINT_OUT = 1;
export const USB_TRANSFER_SIZE = 1024;
