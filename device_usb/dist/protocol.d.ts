import { type WireFrame, type DeviceInfo, type VersionInfo, type DeviceTime, type FileInfo, type FileCount, type CardInfo, type DeviceSettings, type CommandResult, type DeleteFileResult, type FirmwareUpgradeResult, type UacUpdateResult } from "./types.js";
export declare function toBCD(str: string): number[];
export declare function fromBCD(...bytes: number[]): string;
export declare function encodeFrame(commandId: number, sequence: number, body?: number[] | Uint8Array): Uint8Array;
/**
 * Attempt to decode one frame from a byte buffer.
 * Returns the frame and the number of bytes consumed, or null if incomplete.
 */
export declare function decodeFrame(buffer: number[]): {
    frame: WireFrame;
    consumed: number;
} | null;
export declare function parseDeviceInfo(body: number[]): DeviceInfo;
export declare function parseVersionInfo(body: number[]): VersionInfo;
export declare function parseTime(body: number[]): DeviceTime;
export declare function parseFileCount(body: number[]): FileCount;
export declare function parseCardInfo(body: number[]): CardInfo;
export declare function parseSettings(body: number[]): DeviceSettings;
export declare function parseCommandResult(body: number[]): CommandResult & {
    rawCode: number;
    rawBody: string;
};
export declare function parseDeleteFile(body: number[]): DeleteFileResult;
export declare function parseFirmwareUpgrade(body: number[]): FirmwareUpgradeResult;
export declare function parseUacUpdate(body: number[]): UacUpdateResult;
export declare function parseFileList(body: number[]): FileInfo[];
export type ParsedResponse = {
    type: "deviceInfo";
    data: DeviceInfo;
} | {
    type: "versionInfo";
    data: VersionInfo;
} | {
    type: "time";
    data: DeviceTime;
} | {
    type: "setTime";
    data: CommandResult;
} | {
    type: "fileList";
    data: FileInfo[];
} | {
    type: "fileCount";
    data: FileCount;
} | {
    type: "deleteFile";
    data: DeleteFileResult;
} | {
    type: "firmwareUpgrade";
    data: FirmwareUpgradeResult;
} | {
    type: "firmwareUpload";
    data: CommandResult;
} | {
    type: "settings";
    data: DeviceSettings;
} | {
    type: "cardInfo";
    data: CardInfo;
} | {
    type: "uacUpdate";
    data: UacUpdateResult;
} | {
    type: "commandResult";
    data: CommandResult;
} | {
    type: "unknown";
    data: {
        commandId: number;
        body: number[];
    };
};
export declare function parseResponse(commandId: number, body: number[]): ParsedResponse;
export declare function formatDateForDevice(date: Date): number[];
export declare function buildSettingsPayload(opts: {
    autoRecord?: boolean;
    autoPlay?: boolean;
    notification?: boolean;
}): number[];
