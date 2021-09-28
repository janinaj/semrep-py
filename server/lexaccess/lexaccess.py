
from jsonrpclib.SimpleJSONRPCServer import SimpleJSONRPCServer
import optparse
import os.path
import pexpect
import time

class LexAccess():
    def __init__(self, path):
        # spawn the server
        self.process = pexpect.spawn(path, encoding='utf-8')
        self.process.readline()
        self.process.readline()
        # self.process.setecho(False)
        # self.process.expect('done')
        # self.process.expect('\r\n')

    def parse(self, text):
        # Clear any pending output
        try:
            self.process.read_nonblocking(2048, 0)
        except:
            pass

        self.process.sendline(text)
        self.process.readline()
        #self.process.expect(u'</lexRecords>')
        self.process.expect('</lexRecords>')
        # self.process.expect(u'----------')
        

        # Workaround pexpect bug
        # self.process.waitnoecho()

        # Long text also needs increase in socket timeout
        # timeout = 5 + len(text) / 20.0

        # self.process.expect(u'----------', timeout)
        results = self.process.before + self.process.after
        
        self.process.readline()

        return results

def main():
    parser = optparse.OptionParser(usage="%prog [OPTIONS]")
    parser.add_option('-p', '--port', type="int", default=8085,
                      help="Port to bind to [8083]")
    # parser.add_option('--path', default=DIRECTORY,
    #                   help="Path to OpenNLP install [%s]" % DIRECTORY)


    #path = '/Users/mjsarol/Documents/BioNLP/lexAccess2016/bin/LexAccess -f:id -f:x'
    path = 'lexAccess -f:id -f:x'
    # path = 'java -cp /Users/mjsarol/Documents/BioNLP/lexAccess2016/lib/lexAccess2016api.jar:/Users/mjsarol/Documents/BioNLP/lexAccess2016/lib/Other/lexCheck2016api.jar:/Users/mjsarol/Documents/BioNLP/lexAccess2016/lib/jdbcDrivers/HSqlDb/hsqldb.jar:/Users/mjsarol/Documents/BioNLP/lexicon-wrapper Test'
    options, args = parser.parse_args()

    addr = ('localhost', options.port)
    uri = 'http://%s:%s' % addr

    server = SimpleJSONRPCServer(addr)

    print("Starting LexAccess")
    nlp = LexAccess(path)
    server.register_function(nlp.parse)

    print("Serving on %s" % uri)
    server.serve_forever()
	
if __name__ == '__main__':
    main()
