import { CommandId, type WireFrame } from "./types.js";
import { parseFileList } from "./protocol.js";
import type { FileInfo } from "./types.js";
import { UsbTransport } from "./transport.js";

/** HiDock device over USB — list, download, and delete recordings. */
export class HiDockDevice {
  private transport = new UsbTransport();
  private fileListAccumulator: FileListAccumulator | null = null;

  get isConnected(): boolean {
    return this.transport.isConnected;
  }

  get deviceModel() {
    return this.transport.deviceModel;
  }

  async connect(): Promise<void> {
    await this.transport.connect();
  }

  async disconnect(): Promise<void> {
    await this.transport.disconnect();
  }

  getFileCount(timeoutSec = 5) {
    return this.transport.sendCommand(CommandId.QueryFileCount, [], timeoutSec);
  }

  getCardInfo(timeoutSec = 5) {
    return this.transport.sendCommand(CommandId.ReadCardInfo, [], timeoutSec);
  }

  async listFiles(timeoutSec = 30): Promise<FileInfo[] | null> {
    if (!this.transport.isConnected) throw new Error("Device not connected");
    if (this.fileListAccumulator) throw new Error("File list request already in progress");

    const countResp = await this.getFileCount(5);
    if (!countResp || countResp.type !== "fileCount") return null;
    const expectedCount = countResp.data.count;
    if (expectedCount === 0) return [];

    return new Promise<FileInfo[] | null>((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.transport.removeFrameHandler(handler);
        this.fileListAccumulator = null;
        resolve(null);
      }, timeoutSec * 1000);

      this.fileListAccumulator = {
        expectedCount,
        bodyChunks: [],
        resolve: (files) => {
          clearTimeout(timeout);
          this.transport.removeFrameHandler(handler);
          this.fileListAccumulator = null;
          resolve(files);
        },
        reject: (err) => {
          clearTimeout(timeout);
          this.transport.removeFrameHandler(handler);
          this.fileListAccumulator = null;
          reject(err);
        },
        timeout,
      };

      const handler = (frame: WireFrame): boolean => {
        if (frame.commandId !== CommandId.QueryFileList || !this.fileListAccumulator) return false;
        this.fileListAccumulator.bodyChunks.push(frame.body);
        this.tryResolveFileList();
        return true;
      };

      this.transport.onFrame(handler);
      this.transport.sendRaw(CommandId.QueryFileList).catch((err) => {
        clearTimeout(timeout);
        this.transport.removeFrameHandler(handler);
        this.fileListAccumulator = null;
        reject(err);
      });
    });
  }

  downloadFile(
    filename: string,
    expectedLength: number,
    timeoutSec = 600,
    onProgress?: (received: number, total: number) => void,
  ): Promise<Buffer> {
    const fnameBody = Array.from(filename, (c) => c.charCodeAt(0));
    const chunks: Buffer[] = [];
    let received = 0;

    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.transport.removeFrameHandler(handler);
        reject(
          new Error(
            `downloadFile(${filename}): timeout after ${timeoutSec}s (${received}/${expectedLength} bytes)`,
          ),
        );
      }, timeoutSec * 1000);

      const handler = (frame: WireFrame): boolean => {
        if (
          frame.commandId !== CommandId.TransferFile &&
          frame.commandId !== CommandId.GetFileBlock
        ) {
          return false;
        }
        const buf = Buffer.from(frame.body);
        if (buf.length === 0) return true;
        chunks.push(buf);
        received += buf.length;
        onProgress?.(received, expectedLength);
        if (received >= expectedLength) {
          clearTimeout(timeout);
          this.transport.removeFrameHandler(handler);
          const data = Buffer.concat(chunks);
          resolve(data.subarray(0, expectedLength));
        }
        return true;
      };

      this.transport.onFrame(handler);

      this.transport.sendRaw(CommandId.TransferFile, fnameBody).catch((err: unknown) => {
        clearTimeout(timeout);
        this.transport.removeFrameHandler(handler);
        reject(err instanceof Error ? err : new Error(String(err)));
      });
    });
  }

  deleteFile(filename: string, timeoutSec = 10) {
    const body = Array.from(filename, (c) => c.charCodeAt(0));
    return this.transport.sendCommand(CommandId.DeleteFile, body, timeoutSec);
  }

  private tryResolveFileList(): void {
    if (!this.fileListAccumulator) return;
    const { expectedCount, bodyChunks } = this.fileListAccumulator;

    const combined: number[] = [];
    for (const chunk of bodyChunks) {
      for (const b of chunk) combined.push(b);
    }

    const files = parseFileList(combined);
    if (files.length >= expectedCount) {
      this.fileListAccumulator.resolve(files);
    }
  }
}

interface FileListAccumulator {
  expectedCount: number;
  bodyChunks: number[][];
  resolve: (files: FileInfo[]) => void;
  reject: (err: Error) => void;
  timeout: ReturnType<typeof setTimeout>;
}
