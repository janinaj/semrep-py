#try ts t2 by mimicing the server/lexacess code:
from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer 
import optparse
import os.path
import pexpect
import time
path = 'lexAccess -f:id -f:x'
process = pexpect.spawn(path, encoding='utf-8')
process.readline()
process.readline()

def parse(txt):
        # Clear any pending output
        try:
            process.read_nonblocking(2048, 0)
        except:
            pass

        process.sendline(text)
        process.readline()
        #self.process.expect(u'</lexRecords>')
        process.expect('</lexRecords>')
        # self.process.expect(u'----------')


        # Workaround pexpect bug
        # self.process.waitnoecho()

        # Long text also needs increase in socket timeout
        # timeout = 5 + len(text) / 20.0

        # self.process.expect(u'----------', timeout)
        results = process.before + process.after

        process.readline()

        return results

port=8085
addr = ('localhost', port)
uri = 'http://%s:%s' % addr

server = SimpleJSONRPCServer(addr)
print("Starting LexAccess")
#nlp = LexAccess(path)
#server.register_function(nlp.parse)
server.register_function(parse)
print("Serving on %s" % uri)
server.serve_forever()

