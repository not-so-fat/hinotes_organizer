export type HiDockModel = "hidock-h1" | "hidock-h1e" | "hidock-p1" | "hidock-p1:mini" | "unknown";
export declare const ProductIdToModel: Record<number, HiDockModel>;
export declare const VENDOR_ID = 4310;
export declare enum CommandId {
    QueryDeviceInfo = 1,
    QueryDeviceTime = 2,
    SetDeviceTime = 3,
    QueryFileList = 4,
    TransferFile = 5,
    QueryFileCount = 6,
    DeleteFile = 7,
    RequestFirmwareUpgrade = 8,
    FirmwareUpload = 9,
    BncDemoTest = 10,
    GetSettings = 11,
    SetSettings = 12,
    GetFileBlock = 13,
    ReadCardInfo = 16,
    FormatCard = 17,
    GetRecordingFile = 18,
    RequestUacUpdate = 24,
    UacUpdate = 25,
    MassStorage = 61455,
    TestFirmwareVersion = 61441
}
/** Two magic bytes that begin every frame: 0x12 0x34 */
export declare const FRAME_HEADER: readonly [18, 52];
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
export interface UacFirmware {
    url: string;
    md5: string;
}
export declare const UAC_FIRMWARES: Partial<Record<HiDockModel, UacFirmware>>;
export declare const USB_CONFIGURATION = 1;
export declare const USB_INTERFACE = 0;
export declare const USB_ALT_INTERFACE = 0;
export declare const USB_ENDPOINT_IN = 2;
export declare const USB_ENDPOINT_OUT = 1;
export declare const USB_TRANSFER_SIZE = 1024;
