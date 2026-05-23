import { FRAME_HEADER, CommandId, } from "./types.js";
// ─── BCD Encoding ────────────────────────────────────────────────────────────
export function toBCD(str) {
    const out = [];
    for (let i = 0; i < str.length; i += 2) {
        const h = (str.charCodeAt(i) - 48) & 0xff;
        const l = (str.charCodeAt(i + 1) - 48) & 0xff;
        out.push((h << 4) | l);
    }
    return out;
}
export function fromBCD(...bytes) {
    let str = "";
    for (const b of bytes) {
        const v = b & 0xff;
        str += ((v >> 4) & 0x0f).toString();
        str += (v & 0x0f).toString();
    }
    return str;
}
// ─── Frame Encoding ──────────────────────────────────────────────────────────
export function encodeFrame(commandId, sequence, body = []) {
    const bodyArr = body instanceof Uint8Array ? Array.from(body) : body;
    const msg = new Uint8Array(2 + 2 + 4 + 4 + bodyArr.length);
    let idx = 0;
    msg[idx++] = FRAME_HEADER[0];
    msg[idx++] = FRAME_HEADER[1];
    msg[idx++] = (commandId >> 8) & 0xff;
    msg[idx++] = commandId & 0xff;
    msg[idx++] = (sequence >> 24) & 0xff;
    msg[idx++] = (sequence >> 16) & 0xff;
    msg[idx++] = (sequence >> 8) & 0xff;
    msg[idx++] = sequence & 0xff;
    const len = bodyArr.length;
    msg[idx++] = (len >> 24) & 0xff;
    msg[idx++] = (len >> 16) & 0xff;
    msg[idx++] = (len >> 8) & 0xff;
    msg[idx++] = len & 0xff;
    for (const b of bodyArr)
        msg[idx++] = b & 0xff;
    return msg;
}
// ─── Frame Decoding ──────────────────────────────────────────────────────────
function readUint16BE(buf, offset) {
    return ((buf[offset] & 0xff) << 8) | (buf[offset + 1] & 0xff);
}
function readUint32BE(buf, offset) {
    let val = 0;
    for (let i = 0; i < 4; i++) {
        val |= (buf[offset + i] & 0xff) << ((3 - i) * 8);
    }
    return val;
}
/**
 * Attempt to decode one frame from a byte buffer.
 * Returns the frame and the number of bytes consumed, or null if incomplete.
 */
export function decodeFrame(buffer) {
    if (buffer.length < 12)
        return null;
    if (buffer[0] !== FRAME_HEADER[0] || buffer[1] !== FRAME_HEADER[1]) {
        throw new Error(`Invalid frame header: 0x${buffer[0].toString(16)} 0x${buffer[1].toString(16)}`);
    }
    const commandId = readUint16BE(buffer, 2);
    const sequence = readUint32BE(buffer, 4);
    const rawLen = readUint32BE(buffer, 8);
    const padding = (rawLen >> 24) & 0xff;
    const bodyLength = rawLen & 0xffffff;
    const totalLength = 12 + bodyLength + padding;
    if (buffer.length < totalLength)
        return null;
    const body = buffer.slice(12, 12 + bodyLength);
    return {
        frame: { commandId, sequence, bodyLength, padding, body },
        consumed: totalLength,
    };
}
// ─── Response Parsers ────────────────────────────────────────────────────────
export function parseDeviceInfo(body) {
    const vc = [];
    let vn = 0;
    for (let i = 0; i < 4; i++) {
        const b = body[i] & 0xff;
        if (i > 0)
            vc.push(String(b));
        vn |= b << ((3 - i) * 8);
    }
    const sn = [];
    for (let i = 0; i < 16; i++) {
        const chr = body[i + 4];
        if (chr > 0)
            sn.push(String.fromCharCode(chr));
    }
    return { versionCode: vc.join("."), versionNumber: vn, sn: sn.join("") };
}
export function parseVersionInfo(body) {
    const versions = [];
    for (let i = 0, s = 0; i < body.length; s++) {
        versions[s] = [];
        for (let k = 0; k < 4 && i < body.length; k++, i++) {
            versions[s].push(body[i] & 0xff);
        }
    }
    const toInt = (arr) => {
        let v = 0;
        for (let i = 0; i < arr.length; i++)
            v |= arr[i] << ((3 - i) * 8);
        return v;
    };
    return {
        bluetooth: versions[0]?.join(".") ?? "None",
        dsp: versions[1]?.join(".") ?? "None",
        uac: versions[2]?.join(".") ?? "None",
        igd: versions[3] ? toInt(versions[3]).toString(16) : "None",
        igu: versions[4] ? toInt(versions[4]).toString(16) : "None",
        earphone: versions[5]?.join(".") ?? "None",
        base: versions[6]?.join(".") ?? "None",
    };
}
export function parseTime(body) {
    const time = fromBCD(body[0] & 0xff, body[1] & 0xff, body[2] & 0xff, body[3] & 0xff, body[4] & 0xff, body[5] & 0xff, body[6] & 0xff);
    return {
        time: time === "00000000000000"
            ? "unknown"
            : time.replace(/^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2}).*$/, "$1-$2-$3 $4:$5:$6"),
    };
}
export function parseFileCount(body) {
    let c = 0;
    for (let i = 0; i < 4; i++) {
        c |= (body[i] & 0xff) << ((3 - i) * 8);
    }
    return { count: c };
}
export function parseCardInfo(body) {
    let i = 0;
    const read32 = () => {
        const v = ((body[i++] & 0xff) << 24) |
            ((body[i++] & 0xff) << 16) |
            ((body[i++] & 0xff) << 8) |
            (body[i++] & 0xff);
        return v;
    };
    const used = read32();
    const capacity = read32();
    const status = read32();
    return { used, capacity, status: status.toString(16) };
}
export function parseSettings(body) {
    return {
        autoRecord: body[3] === 1,
        autoPlay: body[7] === 1,
        notification: body[11] === 1,
    };
}
export function parseCommandResult(body) {
    return {
        result: body[0] === 0x00 ? "success" : "failed",
        rawCode: body[0] & 0xff,
        rawBody: body.map((b) => (b & 0xff).toString(16).padStart(2, "0")).join(" "),
    };
}
export function parseDeleteFile(body) {
    if (body[0] === 0x00)
        return { result: "success" };
    if (body[0] === 0x01)
        return { result: "not-exists" };
    return { result: "failed" };
}
export function parseFirmwareUpgrade(body) {
    const c = body[0];
    if (c === 0x00)
        return { result: "accepted" };
    if (c === 0x01)
        return { result: "wrong-version" };
    if (c === 0x02)
        return { result: "busy" };
    return { result: "unknown" };
}
export function parseUacUpdate(body) {
    const rst = body[0];
    const map = {
        0x00: "success",
        0x01: "length-mismatch",
        0x02: "busy",
        0x03: "card-full",
        0x04: "card-error",
    };
    return { code: rst, result: map[rst] ?? String(rst) };
}
export function parseFileList(body) {
    const files = [];
    const data = body;
    let start = 0;
    if ((data[0] & 0xff) === 0xff && (data[1] & 0xff) === 0xff) {
        start = 6;
    }
    let i = start;
    while (i < data.length) {
        if (i + 4 >= data.length)
            break;
        const ver = data[i++] & 0xff;
        const nameLen = ((data[i++] & 0xff) << 16) | ((data[i++] & 0xff) << 8) | (data[i++] & 0xff);
        const fname = [];
        for (let k = 0; k < nameLen && i < data.length; k++) {
            const c = data[i++] & 0xff;
            if (c > 0)
                fname.push(String.fromCharCode(c));
        }
        if (i + 4 + 6 + 16 > data.length)
            break;
        const flen = ((data[i++] & 0xff) << 24) |
            ((data[i++] & 0xff) << 16) |
            ((data[i++] & 0xff) << 8) |
            (data[i++] & 0xff);
        i += 6; // skip timestamp bytes
        const sign = [];
        for (let k = 0; k < 16; k++, i++) {
            const h = (data[i] & 0xff).toString(16);
            sign.push(h.length === 1 ? "0" + h : h);
        }
        const name = fname.join("");
        let time = null;
        if (/^\d{14}REC\d+\.wav$/i.test(name)) {
            const ts = name.replace(/^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})REC.*$/i, "$1-$2-$3 $4:$5:$6");
            time = new Date(ts);
        }
        else if (/^.*\.hda$/i.test(name)) {
            const ts = name.replace(/^(\d{2})?(\d{2})(\w{3})(\d{2})-(\d{2})(\d{2})(\d{2})-.*\.hda$/i, "20$2 $3 $4 $5:$6:$7");
            time = new Date(ts);
        }
        files.push({ name, time, length: flen, version: ver, signature: sign.join("") });
    }
    return files;
}
export function parseResponse(commandId, body) {
    switch (commandId) {
        case CommandId.QueryDeviceInfo:
            return { type: "deviceInfo", data: parseDeviceInfo(body) };
        case CommandId.TestFirmwareVersion:
            return { type: "versionInfo", data: parseVersionInfo(body) };
        case CommandId.QueryDeviceTime:
            return { type: "time", data: parseTime(body) };
        case CommandId.SetDeviceTime:
            return { type: "setTime", data: parseCommandResult(body) };
        case CommandId.QueryFileList:
            return { type: "fileList", data: parseFileList(body) };
        case CommandId.QueryFileCount:
            return { type: "fileCount", data: parseFileCount(body) };
        case CommandId.DeleteFile:
            return { type: "deleteFile", data: parseDeleteFile(body) };
        case CommandId.RequestFirmwareUpgrade:
            return { type: "firmwareUpgrade", data: parseFirmwareUpgrade(body) };
        case CommandId.FirmwareUpload:
            return { type: "firmwareUpload", data: parseCommandResult(body) };
        case CommandId.GetSettings:
            return { type: "settings", data: parseSettings(body) };
        case CommandId.SetSettings:
            return { type: "commandResult", data: parseCommandResult(body) };
        case CommandId.ReadCardInfo:
            return { type: "cardInfo", data: parseCardInfo(body) };
        case CommandId.FormatCard:
            return { type: "commandResult", data: parseCommandResult(body) };
        case CommandId.RequestUacUpdate:
            return { type: "uacUpdate", data: parseUacUpdate(body) };
        case CommandId.UacUpdate:
            return { type: "commandResult", data: parseCommandResult(body) };
        case CommandId.BncDemoTest:
            return { type: "commandResult", data: parseCommandResult(body) };
        case CommandId.MassStorage:
            return { type: "commandResult", data: parseCommandResult(body) };
        default:
            return { type: "unknown", data: { commandId, body } };
    }
}
// ─── Time Formatting Helper ──────────────────────────────────────────────────
export function formatDateForDevice(date) {
    const pad = (n) => String(n).padStart(2, "0");
    const str = String(date.getFullYear()) +
        pad(date.getMonth() + 1) +
        pad(date.getDate()) +
        pad(date.getHours()) +
        pad(date.getMinutes()) +
        pad(date.getSeconds());
    return toBCD(str);
}
// ─── Settings Payload Builder ────────────────────────────────────────────────
export function buildSettingsPayload(opts) {
    const data = new Array(12).fill(0);
    if (opts.autoRecord !== undefined)
        data[3] = opts.autoRecord ? 1 : 2;
    if (opts.autoPlay !== undefined)
        data[7] = opts.autoPlay ? 1 : 2;
    if (opts.notification !== undefined)
        data[11] = opts.notification ? 1 : 2;
    return data;
}
//# sourceMappingURL=protocol.js.map