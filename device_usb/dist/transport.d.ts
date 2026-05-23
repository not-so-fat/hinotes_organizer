import { type HiDockModel, type WireFrame } from "./types.js";
import { type ParsedResponse } from "./protocol.js";
export type FrameHandler = (frame: WireFrame) => boolean;
export declare class UsbTransport {
    private device;
    private iface;
    private epIn;
    private epOut;
    private model;
    private sequence;
    private buffer;
    private tasks;
    private listening;
    private frameHandlers;
    get isConnected(): boolean;
    get deviceModel(): HiDockModel;
    /**
     * Register a handler that intercepts incoming frames before default dispatch.
     * Return true from the handler to consume the frame, false to pass it through.
     */
    onFrame(handler: FrameHandler): void;
    removeFrameHandler(handler: FrameHandler): void;
    connect(): Promise<void>;
    disconnect(): Promise<void>;
    sendCommand(commandId: number, body: number[], timeoutSec: number): Promise<ParsedResponse | null>;
    /**
     * Send a raw frame without registering a task for the response.
     * Used by protocols that handle their own response accumulation.
     */
    sendRaw(commandId: number, body?: number[]): Promise<void>;
    private startListening;
    private poll;
    private processBuffer;
}
