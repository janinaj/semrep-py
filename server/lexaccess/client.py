from jsonrpclib.jsonrpc import ServerProxy
from pprint import pprint


class OpenNLP:
    def __init__(self, host='localhost', port=8080):
        uri = "http://%s:%d" % (host, port)
        self.server = ServerProxy(uri)

    def parse(self, text):
        return self.server.parse(text)

if __name__ == '__main__':
    nlp = OpenNLP()
    results = nlp.parse("Rockwell_NNP said_VBD the_DT agreement_NN calls_VBZ for_IN it_PRP to_TO supply_VB 200_CD additional_JJ so-called_JJ shipsets_NNS for_IN the_DT planes_NNS ._.")
    print(results)
