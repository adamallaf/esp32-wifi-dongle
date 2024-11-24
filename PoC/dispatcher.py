class Dispatcher:
    def __init__(self, transport):
        self.__callbacks = []
        self.__transport = transport

    def register(self, callback):
        self.__callbacks.append(callback)

    def dispatch(self):
        while self.__transport.is_open:
            msg = self.__transport.recv()
            for cb in self.__callbacks:
                cb(msg)
