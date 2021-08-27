from jsonrpclib.jsonrpc import ServerProxy

class ServerProxyClient:
    def __init__(self, host, port):
        self.host = host
        self.server = ServerProxy("http://%s:%d" % (host, port))

    def parse(self, text):
        return self.server.parse(self.host)