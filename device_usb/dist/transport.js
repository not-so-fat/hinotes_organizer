import { usb } from "usb";
import { VENDOR_ID, ProductIdToModel, USB_INTERFACE, USB_ENDPOINT_IN, USB_ENDPOINT_OUT, USB_TRANSFER_SIZE, } from "./types.js";
import { encodeFrame, decodeFrame, parseResponse } from "./protocol.js";
export class UsbTransport {
    device = null;
    iface = null;
    epIn = null;
    epOut = null;
    model = "unknown";
    sequence = 1;
    buffer = [];
    tasks = new Map();
    listening = false;
    frameHandlers = [];
    get isConnected() {
        return this.device !== null;
    }
    get deviceModel() {
        return this.model;
    }
    /**
     * Register a handler that intercepts incoming frames before default dispatch.
     * Return true from the handler to consume the frame, false to pass it through.
     */
    onFrame(handler) {
        this.frameHandlers.push(handler);
    }
    removeFrameHandler(handler) {
        this.frameHandlers = this.frameHandlers.filter((h) => h !== handler);
    }
    async connect() {
        const devices = usb.getDeviceList();
        const found = devices.find((d) => d.deviceDescriptor.idVendor === VENDOR_ID);
        if (!found)
            throw new Error("No HiDock device found on USB bus");
        this.device = found;
        this.model = ProductIdToModel[found.deviceDescriptor.idProduct] ?? "unknown";
        this.device.open();
        this.iface = this.device.interface(USB_INTERFACE);
        this.iface.claim();
        this.epIn = this.iface.endpoint(USB_ENDPOINT_IN | 0x80);
        this.epOut = this.iface.endpoint(USB_ENDPOINT_OUT);
        this.buffer = [];
        this.startListening();
    }
    async disconnect() {
        this.listening = false;
        for (const [, task] of this.tasks) {
            if (task.timeout)
                clearTimeout(task.timeout);
            task.resolve(null);
        }
        this.tasks.clear();
        this.frameHandlers = [];
        this.buffer = [];
        // Let any in-flight bulk read finish without starting another poll.
        await new Promise((resolve) => setTimeout(resolve, 250));
        await new Promise((resolve) => {
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
            }
            catch {
                clearTimeout(timeout);
                resolve();
            }
        });
        try {
            this.device?.close();
        }
        catch {
            // best-effort cleanup
        }
        this.device = null;
        this.iface = null;
        this.epIn = null;
        this.epOut = null;
    }
    sendCommand(commandId, body, timeoutSec) {
        if (!this.epOut)
            throw new Error("Device not connected");
        const seq = this.sequence++;
        const frame = encodeFrame(commandId, seq, body);
        return new Promise((resolve, reject) => {
            const timeout = timeoutSec > 0
                ? setTimeout(() => {
                    this.tasks.delete(`cmd-${seq}`);
                    resolve(null);
                }, timeoutSec * 1000)
                : undefined;
            this.tasks.set(`cmd-${seq}`, { resolve, reject, timeout });
            this.epOut.transfer(Buffer.from(frame), (err) => {
                if (err) {
                    this.tasks.delete(`cmd-${seq}`);
                    if (timeout)
                        clearTimeout(timeout);
                    reject(err);
                }
            });
        });
    }
    /**
     * Send a raw frame without registering a task for the response.
     * Used by protocols that handle their own response accumulation.
     */
    sendRaw(commandId, body = []) {
        if (!this.epOut)
            throw new Error("Device not connected");
        const seq = this.sequence++;
        const frame = encodeFrame(commandId, seq, body);
        return new Promise((resolve, reject) => {
            this.epOut.transfer(Buffer.from(frame), (err) => {
                if (err)
                    reject(err);
                else
                    resolve();
            });
        });
    }
    // ─── Internals ──────────────────────────────────────────────────────────
    startListening() {
        if (!this.epIn || this.listening)
            return;
        this.listening = true;
        this.poll();
    }
    poll() {
        if (!this.listening || !this.epIn)
            return;
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
            if (this.listening)
                this.poll();
        });
    }
    processBuffer() {
        while (true) {
            const result = decodeFrame(this.buffer);
            if (!result)
                break;
            this.buffer.splice(0, result.consumed);
            const { frame } = result;
            const consumed = this.frameHandlers.some((handler) => handler(frame));
            if (consumed)
                continue;
            const parsed = parseResponse(frame.commandId, frame.body);
            const taskKey = `cmd-${frame.sequence}`;
            const task = this.tasks.get(taskKey);
            if (task) {
                this.tasks.delete(taskKey);
                if (task.timeout)
                    clearTimeout(task.timeout);
                task.resolve(parsed);
            }
        }
    }
}
//# sourceMappingURL=transport.js.map