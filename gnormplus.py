from socketclient import SocketClient

class GNormPlus:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def annotate(self, text):
        socket_client = SocketClient(self.host, self.port)
        annotations = socket_client.send(text, True)
        # print(annotations)
        return self.parse_annotations(annotations)

    def parse_annotations(self, annotations):
        parsed_annotations = {}

        field_names = ['id', 'name', 'type']

        for annotation in annotations.split("\n"):
            # if string is empty, skip annotation (should only happen at end of annotations string)
            if annotation.strip() == '':
                continue

            field_values = annotation.split('\t')
            if field_values[3] == 'Gene':
                span = (int(field_values[0]), int(field_values[1]) - int(field_values[0]))
                concept = dict(zip(field_names, field_values[2:]))

                parsed_annotations[span] = concept

        return parsed_annotations