import struct
from enum import IntEnum
from threading import Lock


class MsgCtrl:
    STX = 0x02
    EOT = 0x04
    ACK = 0x06


class MsgTypes(IntEnum):
    CMD = 0xA0
    RSP = 0xA1
    MSG = 0xBB


class Commands(IntEnum):
    SCAN = 0x53
    CONNECT = 0x43
    DISCONNECT = 0x44
    REQUEST = 0x52
    STREAM = 0x45


class TransportProtocol:
    __id: int = 0
    __lock: Lock = Lock()

    @classmethod
    def cmd(cls, msg_id: int, data: bytes = b"") -> bytes:
        data_len = len(data) + 1
        if 255 < data_len:  # DER like format, won't be necessary
            data_len |= 0x820000
        dlen = data_len.to_bytes((data_len.bit_length() + 7) >> 3)
        msg = (
            bytes(
                [
                    cls.__next_id(),
                    MsgTypes.CMD,
                ]
            )
            + dlen
            + msg_id.to_bytes()
            + data
        )
        return MsgCtrl.STX.to_bytes() + msg + cls.crc16(msg)

    @classmethod
    def ack(cls, msg: bytes) -> bytes:
        return MsgCtrl.ACK.to_bytes() + msg[1:3] + cls.crc16(msg[1:3])

    @staticmethod
    def calc_crc16(data: bytes) -> int:
        crc = 0x5725
        apx = len(data) & 1
        _data = struct.unpack(
            ">" + "H" * (len(data) >> 1),
            data[: len(data) - apx],
        )
        for d in _data:
            crc ^= d
        if apx:
            crc ^= data[-1] << 8
        return crc

    @classmethod
    def crc16(cls, data: bytes) -> bytes:
        return cls.calc_crc16(data).to_bytes(
            2,
            byteorder="little",
            signed=False,
        )

    @classmethod
    def __next_id(cls):
        cls.__lock.acquire()
        try:
            return cls.__id
        finally:
            cls.__id = (cls.__id + 1) & 0xFF
            cls.__lock.release()


if __name__ == "__main__":
    tp = TransportProtocol
    d = tp.crc16(b"1234567890")
    print(d)
    d = tp.crc16(b"\xf3\x1110.105.207.99")
    print(d.hex())
    print(tp.crc16(b"\0\xbb\x01\xAA").hex())
    d = tp.cmd(1)
    print(d)
    print(tp.crc16(d[1:-2]) == d[-2:])
    d = tp.ack(d)
    print(d)
    d = tp.cmd(1)
    print(d)
    print(tp.crc16(d[1:-2]) == d[-2:])
    d = tp.ack(d)
    print(d)
    d = tp.cmd(1)
    print(d)
    print(tp.crc16(d[1:-2]) == d[-2:])
    d = tp.ack(d)
    print(d)
