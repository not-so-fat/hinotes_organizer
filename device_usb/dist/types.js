// ─── Device Models ───────────────────────────────────────────────────────────
export const ProductIdToModel = {
    0xb00c: "hidock-h1",
    0xb00d: "hidock-h1e",
    0xb00e: "hidock-p1",
    0xb00f: "hidock-p1:mini",
};
export const VENDOR_ID = 0x10d6;
// ─── Command IDs (host → device) ────────────────────────────────────────────
export var CommandId;
(function (CommandId) {
    CommandId[CommandId["QueryDeviceInfo"] = 1] = "QueryDeviceInfo";
    CommandId[CommandId["QueryDeviceTime"] = 2] = "QueryDeviceTime";
    CommandId[CommandId["SetDeviceTime"] = 3] = "SetDeviceTime";
    CommandId[CommandId["QueryFileList"] = 4] = "QueryFileList";
    CommandId[CommandId["TransferFile"] = 5] = "TransferFile";
    CommandId[CommandId["QueryFileCount"] = 6] = "QueryFileCount";
    CommandId[CommandId["DeleteFile"] = 7] = "DeleteFile";
    CommandId[CommandId["RequestFirmwareUpgrade"] = 8] = "RequestFirmwareUpgrade";
    CommandId[CommandId["FirmwareUpload"] = 9] = "FirmwareUpload";
    CommandId[CommandId["BncDemoTest"] = 10] = "BncDemoTest";
    CommandId[CommandId["GetSettings"] = 11] = "GetSettings";
    CommandId[CommandId["SetSettings"] = 12] = "SetSettings";
    CommandId[CommandId["GetFileBlock"] = 13] = "GetFileBlock";
    CommandId[CommandId["ReadCardInfo"] = 16] = "ReadCardInfo";
    CommandId[CommandId["FormatCard"] = 17] = "FormatCard";
    CommandId[CommandId["GetRecordingFile"] = 18] = "GetRecordingFile";
    CommandId[CommandId["RequestUacUpdate"] = 24] = "RequestUacUpdate";
    CommandId[CommandId["UacUpdate"] = 25] = "UacUpdate";
    CommandId[CommandId["MassStorage"] = 61455] = "MassStorage";
    CommandId[CommandId["TestFirmwareVersion"] = 61441] = "TestFirmwareVersion";
})(CommandId || (CommandId = {}));
// ─── Wire Protocol ───────────────────────────────────────────────────────────
/** Two magic bytes that begin every frame: 0x12 0x34 */
export const FRAME_HEADER = [0x12, 0x34];
export const UAC_FIRMWARES = {
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
//# sourceMappingURL=types.js.map