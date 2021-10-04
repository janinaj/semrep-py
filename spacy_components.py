from spacy.language import Language
from spacy.tokens import Doc
from lexaccess import LexAccess
from multiprocessing import Pool
import re
import json

from opennlpcl import *
from gnormplus import *
from metamaplite import *
from wsd import *

class Chunk:
    def __init__(self, span, chunk_type):
        self.span = span
        self.chunk_type = chunk_type
        self.head = None
        self.modifiers = None

class Word:
    def __init__(self, spans, chunk_role = None):
        # span is a list of spans, for flexibility, i.e., in case of gapped words
        self.span = spans
        self.chunk_role = chunk_role

class LexiconMatch:
    def __init__(self, span, lexrecord):
        self.span = span
        self.lexrecord = lexrecord

class Concept:
    def __init__(self, span, annotation):
        self.span = span
        self.annotation = annotation

'''
This is a pipeline component that looks up tokens in the lexicon.

We specifically use LexAccess for lexicon matching.
'''
@Language.factory('lexmatcher', default_config = {'path' : None})
def create_lexmatcher_component(nlp: Language, name: str,path: str):
    Doc.set_extension('lexmatches', default = [])

    return LexMatcherComponent(nlp, path)

class LexMatcherComponent:
    def __init__(self, nlp: Language, path: str):
        self.lexmatcher = LexAccess(path)

    def add_match(self, doc:Doc , prev_lexrecords: list, prev_token_index: int, cur_token_index: int):
        text = doc[prev_token_index:cur_token_index]
        if len(text) == 1:
            allowed_pos = doc[prev_token_index].tag_
        else:
            allowed_pos = None

        lexrecords = self.lexmatcher.parse_lexrecords(prev_lexrecords, text.text, allowed_pos)

        doc._.lexmatches.append(LexiconMatch(text, lexrecords))

    def __call__(self, doc: Doc) -> Doc:
        # find a match for each token, either by itself or as part of a phrase
        for sentence in doc.sents:
            cur_token_index = sentence.start
            prev_token_index = sentence.start
            prev_lexrecords = None

            while cur_token_index < sentence.end:
                lookup_text = doc[prev_token_index:cur_token_index + 1].text

                lexrecords_xml = self.lexmatcher.get_matches(lookup_text)

                # if we find a record, try and match a longer string
                if lexrecords_xml is not None:
                    prev_lexrecords = lexrecords_xml
                    cur_token_index += 1
                    continue

                # if not, save the current record (if any)
                if prev_lexrecords is not None:
                    text = doc[prev_token_index:cur_token_index]
                    if len(text) == 1:
                        allowed_pos = doc[prev_token_index].tag_
                    else:
                        allowed_pos = None

                    lexrecords = self.lexmatcher.parse_lexrecords(prev_lexrecords, text.text, allowed_pos)

                    doc._.lexmatches.append(LexiconMatch(text, lexrecords))
                    prev_lexrecords = None

                    prev_token_index = cur_token_index
                else:
                    prev_token_index += 1
                    cur_token_index += 1

            if prev_lexrecords is not None:
                self.add_match(doc, prev_lexrecords, prev_token_index, cur_token_index)

        return doc

'''
This is a pipeline component that replaces the NER tagging.

For now, it uses GNormPlus and MetaMapLite.
'''
@Language.factory('concept_match', default_config = {'ontologies' : str, 'server_paths' : dict})
def create_concept_match_component(nlp: Language, name: str, ontologies: str, server_paths: dict):
    ## add properties used by SemRep
    Doc.set_extension('concepts', default = [])

    return ConceptMatchComponent(nlp, ontologies, server_paths)

class ConceptMatchComponent:
    def __init__(self, nlp: Language, ontologies: str, server_paths: dict):
        self.ontologies = []
        self.servers = server_paths

        for ontology in ontologies.split(','):
            ontology = ontology.strip()
            self.ontologies.append(globals()[ontology])

    def get_span_from_char_indices(self, doc, char_start_index, char_end_index):
        token_start_index = None
        token_end_index = None
        for token in doc:
            if token_start_index is None:
                if char_start_index > token.idx:
                    continue
                if char_start_index == token.idx:
                    token_start_index = token.i
                if char_start_index < token.idx:
                    token_start_index = token.i - 1
            else:
                if token.idx > char_end_index:
                    return token_start_index, token.i
        if token_start_index is None:
            print('Error: out of boundary character indices')

        return token_start_index, len(doc)

    def __call__(self, doc: Doc) -> Doc:
        processes = {}
        with Pool(processes = len(self.ontologies)) as pool:
            for ontology in self.ontologies:
                processes[ontology.__name__] = pool.apply_async(ontology(self.servers['host'],
                        self.servers[ontology.__name__.lower() + '_port']).annotate, args=(doc.text,))

            annotations = {}
            for ontology in self.ontologies:
                annotations[ontology.__name__] = processes[ontology.__name__].get()

        # wsd -> THIS DOES NOT WORK AGAIN -- NEED TO RECHECK
        # WSD(servers['host'], servers[ontology.__name__.lower() + '_port']).disambiguate(annotations['MetamapLite'], text)

        span_lengths = {}
        for ontology in self.ontologies:
            for (start, length), concept in annotations[ontology.__name__].items():
                if length not in span_lengths:
                    span_lengths[length] = {}
                if (start, start + length) not in span_lengths[length]:
                    span_lengths[length][(start, start + length)] = concept

        sorted_span_lengths = list(span_lengths.keys())
        sorted_span_lengths.sort(reverse = True)

        merged_annotations = {}
        t_annotations = {}
        for span_length in sorted_span_lengths:
            for (start, end), concept in span_lengths[span_length].items():
                cur_span_range = set(range(start, end))

                merge = True
                for (merged_start, merged_end) in merged_annotations.keys():
                    merged_span_range = set(range(merged_start, merged_end))
                    if len(cur_span_range.intersection(merged_span_range)) > 0:
                        # print(f'DONT ADD: {(start, end)}')
                        print(f'DONT ADD: {(start, end)}')
                        merge = False
                        break
                if merge:
                    merged_annotations[(start, end)] = concept
                    t_annotations[f't{start}_{end}'] = concept

        for (char_start_index, char_end_index), annotation in merged_annotations.items():
            token_start_index, token_end_index = self.get_span_from_char_indices(doc,
                                                     char_start_index, char_end_index)
            doc._.concepts.append(Concept(doc[token_start_index:token_end_index], annotation))

        # doc._.concepts = merged_annotations

        with open("an.tmp", 'a') as f:
            f.write(json.dumps(t_annotations, indent=2))  # error, have2change
            f.write('\n')

        return doc

'''
This is a pipeline component that separates the sentences into chunks (e.g. NP, VP).

For now, it uses OpenNLP, but this can be configured to use another chunker.
'''
@Language.factory('chunker', default_config = {'chunker': 'opennlp', 'path' : None})
def create_chunker_component(nlp: Language, name: str, chunker: str, path: str):
    ## add properties used by SemRep
    Doc.set_extension('chunks', default = [])

    if chunker == 'opennlp':
        return OpenNLPChunkerComponent(nlp, path)

class OpenNLPChunkerComponent:
    def __init__(self, nlp: Language, path: str):
        self.chunker = OpenNLP(path)

    def __call__(self, doc: Doc) -> Doc:
        opennlp_input = ''
        for token in doc:
           opennlp_input += f'{token.text}_{token.tag_} '
        chunks = self.chunker.parse(opennlp_input)

        print(f'OpenNLP output: {chunks}')

        # This code does not work for this type of text, need to fix:
        # Hypertension patients take[aspirin]].
        # But for now, it works on most texts.
        cur_token_index = 0
        for chunk in re.findall(r'(?=(\[.*?\]))|(?=(\].*?\[)|(._\.))', chunks):

            # if actual chunk, e.g. [NP Analgesic_JJ aspirin_NN]
            if len(chunk[0]) > 0:
                chunk = chunk[0].strip()[1:-1].split()

                chunk_type = chunk[0]
                chunk_tokens = chunk[1:]

                end_index = cur_token_index + len(chunk_tokens)
                doc._.chunks.append(Chunk(doc[cur_token_index: end_index], chunk_type))

                cur_token_index = end_index

            # if space between chunks, i.e. ] [
            # need example for this case
            elif len(chunk[1]) > 0:
                chunk = chunk[1][1:-1].strip()
                if len(chunk) > 0:
                    cur_token_index += len(chunk.split())

            elif len(chunk[2]) > 0:
                cur_token_index += 1

        return doc

'''
This is a pipeline component that extracts hypernym relations.
'''
@Language.factory('hypernym_analysis')
def create_hypernym_analysis_component(nlp: Language, name: str):
    ## add properties used by SemRep
    Doc.set_extension('hypernyms', default = [])

    return HypernymAnalysisComponent(nlp)

class HypernymAnalysisComponent:
    def __init__(self, nlp: Language):
        pass

    def get_head_index(self, span):
        return len(span) - 1

    def get_concept(self, head, concepts):
        for concept in concepts:
            if head.text == concept.span.text:
                return concept
        return None

    def __call__(self, doc: Doc) -> Doc:
        for chunk in doc._.chunks:
            if chunk.chunk_type == 'NP':
                print(f'chunk: {chunk.span}')
                self.intraNP_hypernymy(chunk, doc)
        # self.interNP_hypernymy(chunk, doc._.concepts)
        return doc

    def intraNP_hypernymy(self, np_chunk, doc):
        if len(np_chunk.span) == 1:
            return None

        # identify head and check associated concept
        head_index = self.get_head_index(np_chunk.span)
        head = np_chunk.span[head_index]

        head_concept = self.get_concept(head, doc._.concepts)

        # if head has no concept -> no hypernym rel
        if head_concept is None:
            return None

        # if concept is symptoms -> no hypernym rel
        # there are too many false positives
        if head_concept.annotation[0]['cui'] == 'C1457887':
            return None

        # identify modifier to the left of head
        modifier = np_chunk.span[head_index - 1]
        modifier_concept = self.get_concept(modifier, doc._.concepts)

        # if modifier has no concept -> no hypernym rel
        if modifier_concept is None:
            return None

        # if modifier and head are the same -> no hypernym rel
        if head_concept.annotation[0]['cui'] == modifier_concept.annotation[0]['cui']:
            return None
        else:
            # check for possible hypernymy
            return self.hypernymy(head_concept.annotation[0], modifier_concept.annotation[0])

    def interNP_hypernymy(self, spacy_sent, np_chunks, concepts, max_distance=5):
        for i in range(len(np_chunks)):
            for j in range(i + 1, i + 6):
                if j == len(np_chunks):
                    break

                # identify head and check associated concept
                head_index = get_head_index(np_chunks[i])
                head = np_chunks[i][head_index]

                head_concept = get_concept(head, concepts)

                # if head has no concept -> no hypernym rel
                if head_concept is None:
                    return None

                # if concept is symptoms -> no hypernym rel
                # there are too many false positives
                if head_concept['cui'] == 'C1457887':
                    return None

                # identify modifier to the left of head
                modifier_index = get_head_index(np_chunks[j])
                modifier = np_chunks[j][modifier_index]
                modifier_concept = get_concept(modifier, concepts)

                # if modifier has no concept -> no hypernym rel
                if modifier_concept is None:
                    return None

                # if modifier and head are the same -> no hypernym rel
                if head_concept['cui'] == modifier_concept['cui']:
                    return None

                if np_chunks[j][-1].i < len(spacy_sent) - 1:
                    ip_type = get_intervening_phrase_type(
                        spacy_sent[np_chunks[i][-1].i + 1:np_chunks[j][0].i].text.strip(),
                        spacy_sent[np_chunks[j][-1].i + 1].text)
                else:
                    ip_type = get_intervening_phrase_type(
                        spacy_sent[np_chunks[i][-1].i + 1:np_chunks[j][0].i].text.strip(),
                        '')

                if ip_type == 'APPOS' or ip_type == 'PAREN':
                    hypernymy(head_concept, modifier_concept)
                else:
                    hypernymy(head_concept, modifier_concept, False)

    def hypernymy(self, concept_1, concept_2, both_directions=True):
        # get the common semantic groups of the concepts
        sem_groups = set(concept_1['semgroups']).intersection(set(concept_2['semgroups']))

        # proceed if there are any common sem groups that are not 'anat' or 'conc'
        if len(sem_groups - set(['anat', 'conc'])) == 0:
            return None

        socket_client = SocketClient('ec2-18-223-119-81.us-east-2.compute.amazonaws.com', '12349')
        if socket_client.send(concept_1['cui'] + concept_2['cui'], True) == 'true':
            print(f"{concept_1['concept_string']} is a {concept_2['concept_string']}")
        elif both_directions and socket_client.send(concept_2['cui'] + concept_1['cui'], True) == 'true':
            print(f"{concept_2['concept_string']} is a {concept_1['concept_string']}")

    def get_intervening_phrase_type(intervening_phrase, after_phrase):
        if is_appositive(intervening_phrase, after_phrase):
            return 'APPOS'
        elif not has_balanced_parenthesis(intervening_phrase):
            return 'PAREN'
        else:
            return 'OTHER'

    def is_appositive(intervening_phrase, after_phrase):
        if intervening_phrase in punctuation and after_phrase == ',':
            return True
        if intervening_phrase in LEFT_PARENTHESES:
            return True
        if intervening_phrase in APPOSITIVE_INDICATORS:
            return True
        return False

    def has_balanced_parenthesis(intervening_phrase):
        parenthesis = re.sub(r'[^' + ''.join([f'\{p}' for p in LEFT_PARENTHESES + RIGHT_PARENTHESES]) + ']',
                             '', intervening_phrase)

        if len(parenthesis) % 2 == 1:
            return False
        else:
            while len(parenthesis) != 0:
                if parenthesis[0] != parenthesis[-1]:
                    return False
                else:
                    parenthesis = parenthesis[1:-1]

        return True