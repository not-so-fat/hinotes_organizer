import { usb, type Device, type InEndpoint, type OutEndpoint, type Interface } from "usb";
import {
  VENDOR_ID,
  ProductIdToModel,
  USB_INTERFACE,
  USB_ENDPOINT_IN,
  USB_ENDPOINT_OUT,
  USB_TRANSFER_SIZE,
  type HiDockModel,
  type WireFrame,
} from "./types.js";
import { encodeFrame, decodeFrame, parseResponse, type ParsedResponse } from "./protocol.js";

interface PendingTask {
  resolve: (value: ParsedResponse | null) => void;
  reject: (err: Error) => void;
  timeout?: ReturnType<typeof setTimeout>;
}

export type FrameHandler = (frame: WireFrame) => boolean;

export class UsbTransport {
  private device: Device | null = null;
  private iface: Interface | null = null;
  private epIn: InEndpoint | null = null;
  private epOut: OutEndpoint | null = null;
  private model: HiDockModel = "unknown";
  private sequence = 1;
  private buffer: number[] = [];
  private tasks = new Map<string, PendingTask>();
  private listening = false;
  private frameHandlers: FrameHandler[] = [];

  get isConnected(): boolean {
    return this.device !== null;
  }

  get deviceModel(): HiDockModel {
    return this.model;
  }

  /**
   * Register a handler that intercepts incoming frames before default dispatch.
   * Return true from the handler to consume the frame, false to pass it through.
   */
  onFrame(handler: FrameHandler): void {
    this.frameHandlers.push(handler);
  }

  removeFrameHandler(handler: FrameHandler): void {
    this.frameHandlers = this.frameHandlers.filter((h) => h !== handler);
  }

  async connect(): Promise<void> {
    const devices = usb.getDeviceList();
    const found = devices.find((d) => d.deviceDescriptor.idVendor === VENDOR_ID);
    if (!found) throw new Error("No HiDock device found on USB bus");

    this.device = found;
    this.model = ProductIdToModel[found.deviceDescriptor.idProduct] ?? "unknown";

    this.device.open();
    this.iface = this.device.interface(USB_INTERFACE);
    this.iface.claim();

    this.epIn = this.iface.endpoint(USB_ENDPOINT_IN | 0x80) as InEndpoint;
    this.epOut = this.iface.endpoint(USB_ENDPOINT_OUT) as OutEndpoint;

    this.buffer = [];
    this.startListening();
  }

  async disconnect(): Promise<void> {
    this.listening = false;
    for (const [, task] of this.tasks) {
      if (task.timeout) clearTimeout(task.timeout);
      task.resolve(null);
    }
    this.tasks.clear();
    this.frameHandlers = [];
    this.buffer = [];

    // Let any in-flight bulk read finish without starting another poll.
    await new Promise((resolve) => setTimeout(resolve, 250));

    await new Promise<void>((resolve) => {
      const timeout = setTimeout(() => resolve(), 5000);
      try {
        if (!this.iface) {
          clearTimeout(timeout);
          resolve();
          return;
        }
        this.iface.release(true, () => {
          clearTimeout(timeout);
          resolve();
        });
      } catch {
        clearTimeout(timeout);
        resolve();
      }
    });

    try {
      this.device?.close();
    } catch {
      // best-effort cleanup
    }
    this.device = null;
    this.iface = null;
    this.epIn = null;
    this.epOut = null;
  }

  sendCommand(
    commandId: number,
    body: number[],
    timeoutSec: number,
  ): Promise<ParsedResponse | null> {
    if (!this.epOut) throw new Error("Device not connected");

    const seq = this.sequence++;
    const frame = encodeFrame(commandId, seq, body);

    return new Promise<ParsedResponse | null>((resolve, reject) => {
      const timeout =
        timeoutSec > 0
          ? setTimeout(() => {
              this.tasks.delete(`cmd-${seq}`);
              resolve(null);
            }, timeoutSec * 1000)
          : undefined;

      this.tasks.set(`cmd-${seq}`, { resolve, reject, timeout });

      this.epOut!.transfer(Buffer.from(frame), (err) => {
        if (err) {
          this.tasks.delete(`cmd-${seq}`);
          if (timeout) clearTimeout(timeout);
          reject(err);
        }
      });
    });
  }

  /**
   * Send a raw frame without registering a task for the response.
   * Used by protocols that handle their own response accumulation.
   */
  sendRaw(commandId: number, body: number[] = []): Promise<void> {
    if (!this.epOut) throw new Error("Device not connected");

    const seq = this.sequence++;
    const frame = encodeFrame(commandId, seq, body);

    return new Promise<void>((resolve, reject) => {
      this.epOut!.transfer(Buffer.from(frame), (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }

  // ─── Internals ──────────────────────────────────────────────────────────

  private startListening(): void {
    if (!this.epIn || this.listening) return;
    this.listening = true;
    this.poll();
  }

  private poll(): void {
    if (!this.listening || !this.epIn) return;

    this.epIn.transfer(USB_TRANSFER_SIZE, (err, data) => {
      if (err) {
        if (this.listening) {
          setTimeout(() => this.poll(), 100);
        }
        return;
      }
      if (data) {
        for (let i = 0; i < data.length; i++) {
          this.buffer.push(data[i]);
        }
        this.processBuffer();
      }
      if (this.listening) this.poll();
    });
  }

  private processBuffer(): void {
    while (true) {
      const result = decodeFrame(this.buffer);
      if (!result) break;

      this.buffer.splice(0, result.consumed);
      const { frame } = result;

      const consumed = this.frameHandlers.some((handler) => handler(frame));
      if (consumed) continue;

      const parsed = parseResponse(frame.commandId, frame.body);
      const taskKey = `cmd-${frame.sequence}`;
      const task = this.tasks.get(taskKey);
      if (task) {
        this.tasks.delete(taskKey);
        if (task.timeout) clearTimeout(task.timeout);
        task.resolve(parsed);
      }
    }
  }
}
