import logging
import struct
import threading
import time
from dataclasses import dataclass
from queue import Empty, Queue

from dispatcher import Dispatcher
from protocol import MsgTypes
from protocol import TransportProtocol as TP
from trasnport import Transport

logger = logging.getLogger("WiFiManager")


@dataclass
class WiFiEntry:
    ssid: str
    bssid: str
    rssi: int
    channel: int
    encryption_mode: int


class WiFiManager:
    def __init__(self, transport: Transport):
        self.__ID: int = 0xF0
        self.__msg_que: Queue = Queue()
        self.__transport = transport
        self.__done: threading.Event = threading.Event()
        self.__networks_found: int = 0
        self.__ssid: str = ""
        self.__password: str = ""
        self.__connected: threading.Event = threading.Event()
        self.__ip: str = ""

    @property
    def ip(self) -> str:
        return self.__ip

    def scan(self):
        self.__networks_found = 0
        cmd = TP.cmd(self.__ID, b"")
        self.__transport.send(cmd)
        self.__done.clear()

    def connect(self, ssid: str, password: str) -> bool:
        self.__ssid = ssid
        self.__password = password
        self.__connected.clear()
        data = self.__ssid.encode() + b"\0" + self.__password.encode() + b"\0"
        for i in range(5):
            cmd = TP.cmd(self.__ID | 2, data)
            self.__transport.send(cmd)
            if self.__connected.wait(15.0):
                break
        return self.is_connected

    def disconnect(self) -> bool:
        if self.is_connected:
            cmd = TP.cmd(self.__ID | 4)
            self.__transport.send(cmd)
        return not self.is_connected

    @property
    def is_connected(self) -> bool:
        return self.__connected.is_set()

    def get_scan_results(self) -> list[WiFiEntry]:
        entries = []
        self.__done.clear()
        self.__done.wait(10.0)
        while not self.__msg_que.empty():
            try:
                entries.append(self.__msg_que.get(timeout=1))
            except Empty:
                break
        return entries

    def wait_until_scan_complete(self, timeout: float = 10.0) -> int:
        self.__done.wait(timeout)
        return self.__networks_found

    def parse(self, data: bytes):
        if data[1] != MsgTypes.RSP:
            return

        msg_len = data[2]
        if data[3] == (self.__ID | 1):
            logger.debug("recieved scan result")
            msg = data[4 : 3 + msg_len]
            entry = WiFiEntry(
                ssid=msg[16:-1].decode(),
                bssid=msg[:6].hex(),
                rssi=struct.unpack("<i", msg[6:10])[0],
                channel=struct.unpack("<I", msg[10:14])[0],
                encryption_mode=struct.unpack("<H", msg[14:16])[0],
            )
            self.__msg_que.put_nowait(entry)
            self.__networks_found -= 1
            if self.__networks_found == 0:
                logger.debug("recieved all scanned APs")
                self.__done.set()
        elif data[3] == self.__ID:
            self.__networks_found = data[4]
            logger.debug(
                f"recieved scan response: {self.__networks_found} APs found",
            )
            self.__done.set()
        elif data[3] == (self.__ID | 3):
            logger.debug("recieved connect response")
            if data[4] == 0x11:
                self.__ip = data[5 : 3 + msg_len].decode()
                logger.debug(f"WiFi connected with {self.__ip}")
                self.__connected.set()
        elif data[3] == (self.__ID | 5):
            logger.debug("recieved disconnect response")
            if data[4] == 0x11:
                logger.debug("WiFi diconnected")
                self.__connected.clear()


if __name__ == "__main__":
    log = logging.getLogger()
    fmt = "%(levelname)s %(filename)s:%(lineno)d (%(funcName)s): %(message)s"
    logging.basicConfig(
        format=fmt,
        level=logging.DEBUG,
    )
    with Transport("/dev/ttyUSB0") as transport:
        w = WiFiManager(transport)
        d = Dispatcher(transport)
        d.register(w.parse)
        t = threading.Thread(target=d.dispatch)
        t.start()
        transport.send(TP.cmd(65))
        w.scan()
        time.sleep(1)
        print(f"Found: {w.wait_until_scan_complete()} networks")
        for p in w.get_scan_results():
            print(p)
        transport.send(TP.cmd(1, b"\x00"))
        w.connect("honey", "passowrd")
        time.sleep(1)
        transport.send(TP.cmd(1, b"\x01"))
        w.disconnect()
        time.sleep(1)
    t.join()
