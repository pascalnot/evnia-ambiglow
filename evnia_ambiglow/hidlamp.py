"""Minimal raw-HID LampArray driver for Windows (ctypes only, no dependencies).

Talks to any HID LampArray (usage page 0x59) such as the Philips Evnia
Ambiglow. Report layout is resolved at runtime through the HID parser
(HidP_*), so report IDs and array sizes do not have to be hard-coded.
"""
import ctypes
import ctypes.wintypes as wt
import struct

hid = ctypes.WinDLL("hid.dll")
k32 = ctypes.WinDLL("kernel32.dll", use_last_error=True)
cfg = ctypes.WinDLL("cfgmgr32.dll")

# HID usage page 0x59 (Lighting and Illumination)
PAGE = 0x59
U_LAMP_ARRAY = 0x01
U_ATTR_REPORT = 0x02
U_LAMP_COUNT = 0x03
U_MIN_UPDATE_INTERVAL = 0x08
U_LAMP_ID = 0x21
U_MULTI_UPDATE = 0x50
U_RED, U_GREEN, U_BLUE, U_INTENSITY = 0x51, 0x52, 0x53, 0x54
U_UPDATE_FLAGS = 0x55
U_RANGE_UPDATE = 0x60
U_ID_START, U_ID_END = 0x61, 0x62
U_CONTROL = 0x70
U_AUTONOMOUS = 0x71

INPUT, OUTPUT, FEATURE = 0, 1, 2
HIDP_STATUS_SUCCESS = 0x00110000
FLAG_UPDATE_COMPLETE = 0x01


class GUID(ctypes.Structure):
    _fields_ = [("d1", wt.DWORD), ("d2", wt.WORD), ("d3", wt.WORD), ("d4", ctypes.c_ubyte * 8)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", wt.USHORT), ("UsagePage", wt.USHORT),
                ("InputReportByteLength", wt.USHORT), ("OutputReportByteLength", wt.USHORT),
                ("FeatureReportByteLength", wt.USHORT), ("Reserved", wt.USHORT * 17),
                ("NumberLinkCollectionNodes", wt.USHORT),
                ("NumberInputButtonCaps", wt.USHORT), ("NumberInputValueCaps", wt.USHORT),
                ("NumberInputDataIndices", wt.USHORT),
                ("NumberOutputButtonCaps", wt.USHORT), ("NumberOutputValueCaps", wt.USHORT),
                ("NumberOutputDataIndices", wt.USHORT),
                ("NumberFeatureButtonCaps", wt.USHORT), ("NumberFeatureValueCaps", wt.USHORT),
                ("NumberFeatureDataIndices", wt.USHORT)]


class HIDP_VALUE_CAPS(ctypes.Structure):
    _fields_ = [("UsagePage", wt.USHORT), ("ReportID", ctypes.c_ubyte), ("IsAlias", ctypes.c_ubyte),
                ("BitField", wt.USHORT), ("LinkCollection", wt.USHORT),
                ("LinkUsage", wt.USHORT), ("LinkUsagePage", wt.USHORT),
                ("IsRange", ctypes.c_ubyte), ("IsStringRange", ctypes.c_ubyte),
                ("IsDesignatorRange", ctypes.c_ubyte), ("IsAbsolute", ctypes.c_ubyte),
                ("HasNull", ctypes.c_ubyte), ("Reserved", ctypes.c_ubyte),
                ("BitSize", wt.USHORT), ("ReportCount", wt.USHORT), ("Reserved2", wt.USHORT * 5),
                ("UnitsExp", wt.ULONG), ("Units", wt.ULONG),
                ("LogicalMin", wt.LONG), ("LogicalMax", wt.LONG),
                ("PhysicalMin", wt.LONG), ("PhysicalMax", wt.LONG),
                ("UsageMin", wt.USHORT), ("UsageMax", wt.USHORT),  # NotRange.Usage == UsageMin
                ("_rest", wt.USHORT * 6)]


k32.CreateFileW.restype = wt.HANDLE
k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
hid.HidD_GetPreparsedData.argtypes = [wt.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
hid.HidD_SetFeature.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
hid.HidD_GetFeature.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
hid.HidD_SetOutputReport.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetValueCaps.argtypes = [ctypes.c_int, ctypes.POINTER(HIDP_VALUE_CAPS), ctypes.POINTER(wt.USHORT), ctypes.c_void_p]
hid.HidP_GetValueCaps.restype = wt.ULONG
hid.HidP_GetCaps.restype = wt.ULONG
hid.HidP_InitializeReportForID.argtypes = [ctypes.c_int, ctypes.c_ubyte, ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidP_InitializeReportForID.restype = wt.ULONG
hid.HidP_SetUsageValue.argtypes = [ctypes.c_int, wt.USHORT, wt.USHORT, wt.USHORT, wt.ULONG, ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidP_SetUsageValue.restype = wt.ULONG
hid.HidP_SetUsageValueArray.argtypes = [ctypes.c_int, wt.USHORT, wt.USHORT, wt.USHORT, ctypes.c_void_p, wt.USHORT, ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidP_SetUsageValueArray.restype = wt.ULONG
hid.HidP_GetUsageValue.argtypes = [ctypes.c_int, wt.USHORT, wt.USHORT, wt.USHORT, ctypes.POINTER(wt.ULONG), ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidP_GetUsageValue.restype = wt.ULONG
hid.HidP_GetUsageValueArray.argtypes = [ctypes.c_int, wt.USHORT, wt.USHORT, wt.USHORT, ctypes.c_void_p, wt.USHORT, ctypes.c_void_p, ctypes.c_void_p, wt.ULONG]
hid.HidP_GetUsageValueArray.restype = wt.ULONG

HID_GUID = GUID(0x4D1E55B2, 0xF16F, 0x11CF, (ctypes.c_ubyte * 8)(0x88, 0xCB, 0x00, 0x11, 0x11, 0x00, 0x00, 0x30))


def hid_paths():
    size = wt.ULONG()
    cfg.CM_Get_Device_Interface_List_SizeW(ctypes.byref(size), ctypes.byref(HID_GUID), None, 0)
    buf = ctypes.create_unicode_buffer(size.value)
    cfg.CM_Get_Device_Interface_ListW(ctypes.byref(HID_GUID), None, buf, size, 0)
    return [p for p in ctypes.wstring_at(ctypes.addressof(buf), size.value).split("\0") if p]


def _check(status, what):
    if status != HIDP_STATUS_SUCCESS:
        raise OSError(f"{what} failed: HIDP status 0x{status:08X}")


class LampArray:
    def __init__(self, path):
        self.path = path
        self.h = k32.CreateFileW(path, 0xC0000000, 0x3, None, 3, 0, None)  # RW, share RW, OPEN_EXISTING
        if self.h in (None, wt.HANDLE(-1).value):
            raise OSError(f"open failed ({ctypes.get_last_error()}): {path}")
        self.pp = ctypes.c_void_p()
        if not hid.HidD_GetPreparsedData(self.h, ctypes.byref(self.pp)):
            raise OSError("HidD_GetPreparsedData failed")
        self.caps = HIDP_CAPS()
        _check(hid.HidP_GetCaps(self.pp, ctypes.byref(self.caps)), "HidP_GetCaps")
        self.values = {t: self._value_caps(t) for t in (INPUT, OUTPUT, FEATURE)}

    @classmethod
    def find(cls, vid=None, pid=None):
        for p in hid_paths():
            if vid is not None and f"vid_{vid:04x}" not in p.lower():
                continue
            if pid is not None and f"pid_{pid:04x}" not in p.lower():
                continue
            try:
                dev = cls(p)
            except OSError:
                continue
            if dev.caps.UsagePage == PAGE and dev.caps.Usage == U_LAMP_ARRAY:
                return dev
            dev.close()
        raise RuntimeError("no HID LampArray found")

    def close(self):
        if self.pp:
            hid.HidD_FreePreparsedData(self.pp)
            self.pp = None
        if self.h:
            k32.CloseHandle(self.h)
            self.h = None

    def _value_caps(self, rtype):
        n = (self.caps.NumberInputValueCaps, self.caps.NumberOutputValueCaps, self.caps.NumberFeatureValueCaps)[rtype]
        if not n:
            return []
        arr = (HIDP_VALUE_CAPS * n)()
        cnt = wt.USHORT(n)
        _check(hid.HidP_GetValueCaps(rtype, arr, ctypes.byref(cnt), self.pp), "HidP_GetValueCaps")
        return list(arr[:cnt.value])

    def _report_len(self, rtype):
        return (self.caps.InputReportByteLength, self.caps.OutputReportByteLength, self.caps.FeatureReportByteLength)[rtype]

    def locate(self, usage, collection=None):
        """(report_type, report_id, value_caps) for the first value with this usage,
        optionally restricted to a parent collection usage (e.g. U_MULTI_UPDATE)."""
        for rtype in (FEATURE, OUTPUT, INPUT):
            for vc in self.values[rtype]:
                if collection is not None and vc.LinkUsage != collection:
                    continue
                if vc.UsagePage == PAGE and vc.UsageMin <= usage <= (vc.UsageMax if vc.IsRange else vc.UsageMin):
                    return rtype, vc.ReportID, vc
        raise KeyError(f"usage 0x{usage:02X} not in descriptor")

    # --- report building -------------------------------------------------
    def _new(self, rtype, rid):
        n = self._report_len(rtype)
        buf = (ctypes.c_ubyte * n)()
        _check(hid.HidP_InitializeReportForID(rtype, rid, self.pp, buf, n), "HidP_InitializeReportForID")
        return buf

    def _set(self, rtype, buf, usage, value):
        _check(hid.HidP_SetUsageValue(rtype, PAGE, 0, usage, value, self.pp, buf, len(buf)), f"set 0x{usage:02X}")

    def _set_array(self, rtype, buf, usage, vc, values):
        nbytes = (vc.BitSize * vc.ReportCount + 7) // 8
        packed = _pack_bits(values, vc.BitSize, vc.ReportCount, nbytes)
        _check(hid.HidP_SetUsageValueArray(rtype, PAGE, 0, usage, packed, nbytes, self.pp, buf, len(buf)),
               f"set array 0x{usage:02X}")

    def _send(self, rtype, buf):
        fn = hid.HidD_SetFeature if rtype == FEATURE else hid.HidD_SetOutputReport
        if not fn(self.h, buf, len(buf)):
            raise OSError(f"send report failed ({ctypes.get_last_error()})")

    def _get(self, rid):
        buf = self._new(FEATURE, rid)
        buf[0] = rid
        if not hid.HidD_GetFeature(self.h, buf, len(buf)):
            raise OSError(f"HidD_GetFeature failed ({ctypes.get_last_error()})")
        return buf

    def _get_value(self, buf, usage):
        v = wt.ULONG()
        _check(hid.HidP_GetUsageValue(FEATURE, PAGE, 0, usage, ctypes.byref(v), self.pp, buf, len(buf)), f"get 0x{usage:02X}")
        return v.value

    # --- LampArray operations -------------------------------------------
    def attributes(self):
        _, rid, _ = self.locate(U_LAMP_COUNT)
        buf = self._get(rid)
        return {"lamp_count": self._get_value(buf, U_LAMP_COUNT),
                "min_update_interval_us": self._get_value(buf, U_MIN_UPDATE_INTERVAL)}

    def set_autonomous(self, on):
        rtype, rid, _ = self.locate(U_AUTONOMOUS)
        buf = self._new(rtype, rid)
        self._set(rtype, buf, U_AUTONOMOUS, 1 if on else 0)
        self._send(rtype, buf)

    def set_range(self, start, end, rgb, intensity=255):
        rtype, rid, _ = self.locate(U_ID_START)
        buf = self._new(rtype, rid)
        self._set(rtype, buf, U_UPDATE_FLAGS, FLAG_UPDATE_COMPLETE)
        self._set(rtype, buf, U_ID_START, start)
        self._set(rtype, buf, U_ID_END, end)
        for u, v in zip((U_RED, U_GREEN, U_BLUE, U_INTENSITY), (*rgb, intensity)):
            self._set(rtype, buf, u, v)
        self._send(rtype, buf)

    def multi_slots(self):
        return self._multi_layout()[1]

    def _multi_layout(self):
        """Verify the LampMultiUpdate report matches the Microsoft sample layout:
        [id][LampCount u8][UpdateFlags u8][LampId u16 x N][R G B I] x N.
        The colour fields are N separate items per usage, which HidP cannot
        address individually, so they are packed by hand."""
        if hasattr(self, "_multi"):
            return self._multi
        rtype, rid, id_vc = self.locate(U_LAMP_ID, U_MULTI_UPDATE)
        slots = id_vc.ReportCount
        # HidP can't tell apart usages shared between reports (LampCount, LampId),
        # so check the field sizes and that they add up to the report length.
        in_report = [vc for vc in self.values[FEATURE] if vc.ReportID == rid]
        colours = [vc for vc in in_report if vc.UsageMin in (U_RED, U_GREEN, U_BLUE, U_INTENSITY)]
        length = self._report_len(rtype)
        ok = (rtype == FEATURE and id_vc.BitSize == 16
              and len(colours) == 4 * slots and all(vc.BitSize == 8 for vc in colours)
              and length == 1 + 2 + 2 * slots + 4 * slots)
        if not ok:
            raise RuntimeError("unexpected LampMultiUpdate layout")
        self._multi = (rid, slots, length)
        # The Evnia reports IntensityLevelCount = 1 and its firmware silently
        # drops multi-updates whose intensity exceeds it (255 is ignored, 1 works).
        self.intensity = min(255, max(1, self.lamp_attribute(0, 0x2B)))
        return self._multi

    def _lamp_attributes(self, lamp):
        """Feature-report buffer of the attributes response for one lamp."""
        _, req_id, _ = self.locate(U_LAMP_ID, 0x20)
        _, resp_id, _ = self.locate(0x23)
        length = self._report_len(FEATURE)
        req = bytearray(length)
        req[0] = req_id
        struct.pack_into("<H", req, 1, lamp)
        if not hid.HidD_SetFeature(self.h, (ctypes.c_ubyte * length).from_buffer(req), length):
            raise OSError(f"attributes request failed ({ctypes.get_last_error()})")
        return self._get(resp_id)

    def lamp_attribute(self, lamp, usage):
        return self._get_value(self._lamp_attributes(lamp), usage)

    def lamp_positions(self):
        """[(x, y, z)] in micrometres for every lamp."""
        out = []
        for i in range(self.attributes()["lamp_count"]):
            resp = self._lamp_attributes(i)
            out.append(tuple(self._get_value(resp, u) for u in (0x23, 0x24, 0x25)))
        return out

    def set_colors(self, colors):
        """colors: list of (r, g, b), one per lamp id 0..N-1."""
        self.update(list(enumerate(colors)))

    def update(self, lamps):
        """lamps: [(lamp_id, (r, g, b))]. Sent in as few LampMultiUpdate reports
        as possible; only the last has UpdateComplete, so the device latches
        them all at once. Each report costs ~6 ms on the Evnia firmware."""
        rid, slots, length = self._multi_layout()
        n = len(lamps)
        for start in range(0, n, slots):
            chunk = lamps[start:start + slots]
            last = start + slots >= n
            buf = bytearray(length)
            buf[0] = rid
            buf[1] = len(chunk)
            buf[2] = FLAG_UPDATE_COMPLETE if last else 0
            struct.pack_into(f"<{len(chunk)}H", buf, 3, *(i for i, _ in chunk))
            o = 3 + 2 * slots
            for _, (r, g, b) in chunk:
                buf[o:o + 4] = bytes((r, g, b, self.intensity))
                o += 4
            raw = (ctypes.c_ubyte * length).from_buffer(buf)
            if not hid.HidD_SetFeature(self.h, raw, length):
                raise OSError(f"HidD_SetFeature failed ({ctypes.get_last_error()})")

    def describe(self):
        names = {INPUT: "input", OUTPUT: "output", FEATURE: "feature"}
        c = self.caps
        lines = [self.path,
                 f"usage page 0x{c.UsagePage:02X} usage 0x{c.Usage:02X}  report bytes in/out/feat = "
                 f"{c.InputReportByteLength}/{c.OutputReportByteLength}/{c.FeatureReportByteLength}"]
        for rtype, vcs in self.values.items():
            for vc in vcs:
                um = f"0x{vc.UsageMin:02X}" + (f"-0x{vc.UsageMax:02X}" if vc.IsRange else "")
                lines.append(f"  {names[rtype]:7} id={vc.ReportID:3} page=0x{vc.UsagePage:02X} usage={um:11} "
                             f"bits={vc.BitSize:2} count={vc.ReportCount:3} link=0x{vc.LinkUsage:02X} "
                             f"range=[{vc.LogicalMin},{vc.LogicalMax}]")
        return "\n".join(lines)


def _pack_bits(values, bitsize, count, nbytes):
    if bitsize % 8 == 0:
        w = bitsize // 8
        out = bytearray()
        for v in values[:count]:
            out += int(v).to_bytes(w, "little")
        return (ctypes.c_char * nbytes).from_buffer_copy(bytes(out).ljust(nbytes, b"\0"))
    acc = 0
    for i, v in enumerate(values[:count]):
        acc |= (int(v) & ((1 << bitsize) - 1)) << (i * bitsize)
    return (ctypes.c_char * nbytes).from_buffer_copy(acc.to_bytes(nbytes, "little"))


if __name__ == "__main__":
    dev = LampArray.find()
    print(dev.describe())
    try:
        print(dev.attributes())
    except Exception as e:  # noqa: BLE001
        print("attributes:", e)
    dev.close()
