from visualization.channels.ws import WebSocketHub


class DummyWS:
    def __init__(self):
        self.messages = []
        self.closed = False

    def send(self, msg):
        if self.closed:
            raise RuntimeError('closed')
        self.messages.append(msg)


def test_ws_hub_broadcast_add_remove():
    hub = WebSocketHub()
    ws1 = DummyWS()
    ws2 = DummyWS()

    hub.add(ws1)
    hub.add(ws2)
    hub.broadcast({'hello': 'world'})

    assert ws1.messages and ws2.messages

    hub.remove(ws1)
    ws2.closed = True
    hub.broadcast({'x': 1})

    assert len(ws1.messages) == 1


