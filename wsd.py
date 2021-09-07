from socketclient import SocketClient
import json

class WSD:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def disambiguate(self, annotations, text):
        all_queries = ''
        for (start, end), concepts in annotations.items():
            query = {}

            query['cuis'] = {}
            for concept in concepts:
                query['cuis'][concept['cui']] = concept['name']
            query['cuis'] = json.dumps(query['cuis']).replace("'", "\\'")

            query['sl'] = f'{start}-{end}'
            query['text'] = text[:-1]

            all_queries += json.dumps(query) + '\t\t\t'

        socket_client = SocketClient(self.host, self.port)
        responses = socket_client.send(all_queries)

        for response in responses.split('\t\t\t'):
            response = json.loads(response)

            span = response['sl'].split('-')
            start = int(span[0])
            end = int(span[1])

            for concept in annotations[(start, end)]:
                if concept['name'] == response['names']:
                    annotations[(start, end)] = concept
                    break
        return annotations