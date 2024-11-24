import logging
import pathlib
import time
from queue import Queue
from threading import Event, Thread

import serial
from protocol import MsgCtrl, MsgTypes
from protocol import TransportProtocol as TP

logger = logging.getLogger("Transport")


class Transport:
    def __init__(self, device: str):
        self.__device: str = device
        self.__serial: serial.Serial | None = None
        self.__msg_que: Queue = Queue(maxsize=100)
        self.__open: Event = Event()
        self.__receiver: Thread = Thread(target=self.recv_loop)

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    @property
    def is_open(self) -> bool:
        return self.__open.is_set()

    def open(self):
        if not pathlib.Path(self.__device).is_char_device():
            raise TransportError(f"{self.__device} not found!")
        self.__serial = serial.Serial(
            self.__device,
            baudrate=460800,
            timeout=1,
        )
        self.__open.set()
        self.__receiver.start()

    def close(self):
        if not self.__serial:
            return
        self.__open.clear()
        self.__msg_que.put_nowait(b"\x00" * 4)
        self.__receiver.join(3)
        self.__serial.close()
        self.__serial = None

    def send(self, data: bytes):
        assert self.__serial
        logger.debug(f"writing: {data}")
        self.__serial.write(data)

    def recv(self) -> bytes:
        assert self.__serial
        return self.__msg_que.get()

    def recv_loop(self) -> None:
        assert self.__serial
        while self.__open.is_set():
            b = self.__serial.read()
            if b and b[0] in MsgCtrl.__dict__.values():
                msg = self.__serial.read(2)
                if msg[-1] not in MsgTypes.__dict__.values():
                    logger.error(f"bad msg type: {msg}")
                    continue
                if b[0] == MsgCtrl.STX:  # ACK frames don't contain data
                    if 0x82 == (msg_len := self.__serial.read()):
                        msg_len = self.__serial.read(2)
                    msg += msg_len
                    rsize = int.from_bytes(msg_len)
                    msg += self.__serial.read(rsize)
                if (ccrc := TP.crc16(msg)) != (crc := self.__serial.read(2)):
                    logger.debug(f"bad CRC16: {ccrc} != {crc}; msg: {msg}")
                    continue
                logger.debug(f"received msg: {b + msg + crc}")
                self.__msg_que.put_nowait(msg)


class TransportError(Exception):
    pass


if __name__ == "__main__":
    log = logging.getLogger()
    fmt = "%(levelname)s %(filename)s:%(lineno)d (%(funcName)s): %(message)s"
    logging.basicConfig(
        format=fmt,
        level=logging.DEBUG,
    )
    with Transport("/dev/ttyUSB0") as transport:
        transport.send(b"A"[0])
        print(transport.recv())
        cmd = TP.cmd(1, b"\x00")
        transport.send(cmd)
        print(transport.recv())
        time.sleep(1)
        cmd = TP.cmd(1, b"\x01")
        transport.send(cmd)
        print(transport.recv())
        time.sleep(1)
        cmd = TP.cmd(1, b"\x00")
        transport.send(cmd)
        print(transport.recv())
        time.sleep(1)
        cmd = TP.cmd(1, b"\x01")
        transport.send(cmd)
        print(transport.recv())
        time.sleep(1)
        cmd = TP.cmd(0xF0)
        transport.send(cmd)
        print(transport.recv())
        print(transport.recv())
        print(transport.recv())
        print(transport.recv())
        time.sleep(1)
    logger.debug("done")
