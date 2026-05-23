import type { FileInfo } from "./types.js";
/** HiDock device over USB — list, download, and delete recordings. */
export declare class HiDockDevice {
    private transport;
    private fileListAccumulator;
    get isConnected(): boolean;
    get deviceModel(): import("./types.js").HiDockModel;
    connect(): Promise<void>;
    disconnect(): Promise<void>;
    getFileCount(timeoutSec?: number): Promise<import("./protocol.js").ParsedResponse | null>;
    getCardInfo(timeoutSec?: number): Promise<import("./protocol.js").ParsedResponse | null>;
    listFiles(timeoutSec?: number): Promise<FileInfo[] | null>;
    downloadFile(filename: string, expectedLength: number, timeoutSec?: number, onProgress?: (received: number, total: number) => void): Promise<Buffer>;
    deleteFile(filename: string, timeoutSec?: number): Promise<import("./protocol.js").ParsedResponse | null>;
    private tryResolveFileList;
}
