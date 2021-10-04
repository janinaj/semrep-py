from socketclient import SocketClient
import logging
logging.basicConfig(filename='semrep.log',filemode='a', level=logging.INFO)

class MetamapLite:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def annotate(self, text):
        import json
        socket_client = SocketClient(self.host, self.port)
        annotations = socket_client.send(text)
        # print(annotations)
        print(f'annotate:{type(annotations)}')
        annotations.replace(';;',';\n;') #1st step to being more comparable
        print(f'annotate:{annotations}')
        #logging.debug(f'annotations:\n{annotations}')
        logging.info(f'annotations:{annotations}')
        #with open("log.tmp", 'a') as f:
        #    f.write(annotations)
        #    f.write('\n')
        return self.parse_annotations(annotations)

    def parse_annotations(self, annotations):
        # format: {(start, length) : list<ScoredUMLSConcept>}
        parsed_annotations = {}

        field_names = ['cui', 'name', 'concept_string', 'score', 'semtypes', 'semgroups']

        # fields that contain a list of strings
        field_list_objs = ['semtypes', 'semgroups']
        for annotation in annotations.split(";;"):
            if annotation.endswith(',,'):
                annotation = annotation[:-2]

            # if string is empty, skip annotation (should only happen at end of annotations string)
            if annotation.strip() == '':
                continue

            field_values = annotation.split(',,')

            # span of entity in annotations string
            span = (int(field_values[0]), int(field_values[1]))

            # parse all matched concepts
            concepts = []
            for index in range(2, len(field_values), len(field_names)):
                concept = dict(zip(field_names, field_values[index: index + len(field_names) + 1]))
                for field_name in field_list_objs:
                    concept[field_name] = concept[field_name].split('::')
                concepts.append(concept)

            parsed_annotations[span] = concepts

        return parsed_annotations
