from spacy.language import Language
from spacy.tokens import Doc
from spacy.tokens import Token
from lexaccess import LexAccess
from multiprocessing import Pool
from string import punctuation
import re
import json

from opennlpcl import *
from gnormplus import *
from metamaplite import *
from wsd import *
from srindicator import *

PREDICATIVE_CATEGORIES = set(['NN', 'VB', 'JJ', 'RB', 'PR'])
HEAD_CATEGORIES = set(['IN', 'WD', 'WP', 'WR'])

LEFT_PARENTHESES = ['(', '{', '[']
RIGHT_PARENTHESES = [')', '}', ']']
APPOSITIVE_INDICATORS = ['such as', 'particularly', 'in particular', 'including']

NON_HYPERNYM_CUIS = ['C1457887'] # Symptom
GEOA_HYPERNYMS = ['country', 'countries', 'islands', 'continent', 'locations', 'city', 'cities']

MODHEAD_TYPES = ['process_of', 'inverse:uses', 'location_of', 'inverse:part_of', 'inverse:process_of']

VERBS_TAKING_WITH_IN_PASSIVE = ["alleviate","ameliorate","associate","attenuate","control","cotransfect","co-transfect",
							"eliminate","immunize","manage","mitigate","pretreat","prevent","transfect","treat"]

NOMINAL_SUBJECT_CUES = ["by","with","via"]
NOMINAL_OBJECT_CUES = ["of"]

def get_pos_category(tag):
    return tag[:2]

class Sentence:
    def __init__(self):
        self.words = []
        self.chunks = []

    def add_chunk(self, chunk):
        chunk.sentence_index = len(self.chunks)
        self.chunks.append(chunk)

    def get_previous_chunk(self, chunk):
        if chunk.sentence_index != 0:
            return self.chunks[chunk.sentence_index - 1]
        return None

    def get_next_chunk(self, chunk):
        if chunk.sentence_index != len(self.chunks) - 1:
            return self.chunks[chunk.sentence_index + 1]
        return None

class Chunk:
    def __init__(self, chunk_type):
        # self.span = span
        self.chunk_type = chunk_type
        self.sentence_index = None # index of chunk wrt sentence
        self.head_index = None # index of head word (wrt chunk)
        self.modifiers = []
        self.words = []

    # @property
    # def candidates(self):
    #     return [word for word in self.words if word.associated_concept is not None]

    # set a role for each word in the chunk (either head or modifier)
    def set_chunk_roles(self):
        if len(self.words) == 1:
            self.words[0].chunk_role = 'H'
            self.head_index = 0
        else:
            head_found = False
            for i in range(len(self.words) - 1, -1, -1):
                # if chunk is a noun phrase
                if self.chunk_type == 'NP':
                    if not head_found:
                        if self.words[i].pos_tag.startswith('NN') or \
                            self.words[i].pos_tag.startswith('JJ') or \
                            self.words[i].pos_tag.startswith('VBG'):

                            self.words[i].chunk_role = 'H'
                            self.head_index = i
                            head_found = True
                    elif self.words[i].span.text.isalnum() and self.words[i].pos_tag != 'DT':
                        self.words[i].chunk_role = 'M'
                        self.modifiers.append(self.words[i])
                elif self.chunk_type == 'VP':
                    if not head_found:
                        if self.words[i].pos_tag.startswith('VB'):
                            self.words[i].chunk_role = 'H'
                            self.head_index = i
                            head_found = True
                    elif self.words[i].span.text.isalnum():
                        self.words[i].chunk_role = 'M'
                        self.modifiers.append(self.words[i])
                elif self.chunk_type == 'ADJP':
                    if not head_found:
                        if self.words[i].pos_tag.startswith('JJ'):
                            self.words[i].chunk_role = 'H'
                            self.head_index = i
                            head_found = True
                    elif self.words[i].span.text.isalnum():
                        self.words[i].chunk_role = 'M'
                        self.modifiers.append(self.words[i])
                elif self.chunk_type == 'PP':
                    if not head_found:
                        if self.words[i].pos_tag.startswith('IN'):
                            self.words[i].chunk_role = 'H'
                            self.head_index = i
                            head_found = True
                    elif self.words[i].span.text.isalnum():
                        self.words[i].chunk_role = 'M'
                        self.modifiers.append(self.words[i])
                elif self.chunk_type == 'ADVP':
                    if not head_found:
                        if self.words[i].pos_tag.startswith('RB'):
                            self.words[i].chunk_role = 'H'
                            self.head_index = i
                            head_found = True
                    elif self.words[i].span.text.isalnum():
                        self.words[i].chunk_role = 'M'
                        self.modifiers.append(self.words[i])
            self.modifiers.reverse()

    def is_in_passive_voice(self, sentence):
        if self.chunk_type != 'VP':
            return False
        if not self.words[self.head_index].pos_tag == 'VBN':
            return False

        current_chunk = self
        while True:
            next_chunk = sentence.get_next_chunk(current_chunk)
            if next_chunk is None:
                return False
            if next_chunk.chunk_type == 'ADVP':
                current_chunk = next_chunk
                continue
            else:
                break

        if next_chunk.chunk_type == 'PP' and next_chunk.words[next_chunk.head_index].pos_tag == 'IN' and \
                (next_chunk.words[next_chunk.head_index].span.text == 'by' or
                 (next_chunk.words[next_chunk.head_index].span.text == 'with' and
                    self.words[self.head_index].span.lemma_ in VERBS_TAKING_WITH_IN_PASSIVE)):
            return True
        elif next_chunk.chunk_type == 'VP':
            next_chunk = sentence.get_next_chunk(next_chunk)
            if next_chunk is not None:
                if next_chunk.words[0].lower() == 'using':
                    return True

        return False




class Word:
    def __init__(self, spans, chunk_role = None, associated_concepts = None):
        # span is a list of spans, for flexibility, i.e., in case of gapped words
        self.span = spans
        self.chunk_role = chunk_role
        self.associated_concepts = associated_concepts

        self.set_head()
        self.set_pos_tag()

        # self.predicate_index = None

    def set_pos_tag(self):
        self.pos_tag = self.head.tag_

    def is_entity(self):
        return self.associated_concepts is None
    #
    # def is_predicate(self):
    #     if self.predicate_index is not None:
    #

    def set_head(self):
        for i, token in enumerate(self.span):
            if get_pos_category(token.tag_) in HEAD_CATEGORIES:
                break

        for j in range(i - 1, 0, -1):
            if get_pos_category(self.span[j].tag_) in PREDICATIVE_CATEGORIES:
                self.head = self.span[j]
                return None

        self.head = self.span[len(self.span) - 1]

class LexiconMatch:
    def __init__(self, span, lexrecord):
        self.span = span
        self.lexrecord = lexrecord

class Concept:
    def __init__(self, span, annotation):
        self.span = span
        self.annotation = annotation

class Relation:
    def __init__(self, subject, predicate, object, indicator):
        self.subject = subject
        self.predicate = predicate
        self.object = object
        self.indicator = indicator

class Predicate:
    def __init__(self, word, indicator):
        self.word = word
        self.indicator = indicator
    # def __init__(self, id_, span, type, indicator, sense):
        # self.id = id_
        # self.span = span
        # self.type = type
        # self.indicator = indicator
        # self.sense = sense

'''
This is a pipeline component that looks up tokens in the lexicon.

We specifically use LexAccess for lexicon matching.
'''
@Language.factory('lexmatcher', default_config = {'path' : None})
def create_lexmatcher_component(nlp: Language, name: str, path: str):
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
        print('-----Start: lexicon matching-----')

        # find a match for each token, either by itself or as part of a phrase
        for sentence in doc.sents:
            cur_token_index = sentence.start
            prev_token_index = sentence.start
            prev_lexrecords = None

            while cur_token_index < sentence.end:
                if doc[cur_token_index].text not in punctuation and doc[cur_token_index].text.strip() != '':
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

        print('-----End: lexicon matching-----')

        return doc

'''
This is a pipeline component that replaces the NER tagging.

For now, it uses GNormPlus and MetaMapLite.
'''
@Language.factory('concept_match', default_config = {'ontologies' : str, 'server_paths' : dict})
def create_concept_match_component(nlp: Language, name: str, ontologies: str, server_paths: dict):
    ## add properties used by SemRep
    Doc.set_extension('concepts', default = [])
    Token.set_extension('concept_index', default = None)

    return ConceptMatchComponent(nlp, ontologies, server_paths)

# TO DO: create objects for annotations??
class ConceptMatchComponent:
    def __init__(self, nlp: Language, ontologies: str, server_paths: dict):
        self.ontologies = []
        self.servers = server_paths

        for ontology in ontologies.split(','):
            ontology = ontology.strip()
            self.ontologies.append(globals()[ontology])

    def get_span_from_char_indices(self, doc, char_start_index, char_end_index):
        token_start_index = None
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
                    print(f'cc: {token}')
                    print(f'char: {doc[token_start_index: token.i]}')
                    return token_start_index, token.i
        if token_start_index is None:
            print('Error: out of boundary character indices')

        return token_start_index, len(doc)

    def get_concept_token_span(self, doc, char_start_index, char_end_index):
        token_start_index = None
        for token in doc:
            token_char_indices = range(token.idx, token.idx + len(token) + 1)
            if char_start_index in token_char_indices:
                token_start_index = token.i
            if char_end_index in token_char_indices:
                return token_start_index, token.i + 1

    def __call__(self, doc: Doc) -> Doc:
        print('-----Start: concept matching-----')

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
                    span_lengths[length][(start, start + length)] = {}
                span_lengths[length][(start, start + length)][ontology.__name__] = concept

        sorted_span_lengths = list(span_lengths.keys())
        sorted_span_lengths.sort(reverse = True)

        merged_annotations = set()
        cur_concept_index = 0
        for span_length in sorted_span_lengths:
            for (start, end), concepts in span_lengths[span_length].items():
                cur_span_range = set(range(start, end))

                merge = True
                for (merged_start, merged_end) in merged_annotations:
                    merged_span_range = set(range(merged_start, merged_end))
                    if len(cur_span_range.intersection(merged_span_range)) > 0:
                        merge = False
                        break
                if merge:
                    merged_annotations.add((start, end))
                    token_start_index, token_end_index = self.get_concept_token_span(doc, start, end)
                    doc._.concepts.append(Concept(doc[token_start_index:token_end_index], concepts))

                    for token in doc[token_start_index:token_end_index]:
                        token._.concept_index = cur_concept_index
                    cur_concept_index += 1

                    print(f'concept: {doc[token_start_index:token_end_index]} |  matches: {concepts.keys()}')
                    # for token in doc[token_start_index:token_end_index]:

        print('-----End: concept matching-----')

        return doc


'''
This is a pipeline component that combines tokens into "words" based on lexicon and concept matching.
'''
@Language.factory('harmonizer')
def create_harmonizer_component(nlp: Language, name: str):
    ## add properties used by SemRep
    Doc.set_extension('sentences', default = [])

    # Doc.set_extension('words', default = [])

    return HarmonizerComponent(nlp)

# TO DO: add lexicon harmonization
class HarmonizerComponent:
    def __init__(self, nlp: Language):
        pass

    def __call__(self, doc: Doc) -> Doc:
        print('-----Start: harmonization-----')

        for sent in doc.sents:
            sentence = Sentence()

            i = 0
            while i < len(sent):
                token = sent[i]
                if token._.concept_index is None:
                    concept = None
                    word = Word(doc[token.i:token.i + 1])
                else:
                    concept = doc._.concepts[token._.concept_index]
                    word = Word(concept.span)

                sentence.words.append(Word(word.span, None, concept))
                i += len(word.span)

                print(f'word: {word.span} {word.head} {word.pos_tag}')

            doc._.sentences.append(sentence)

        print('-----End: harmonization-----')

        return doc

'''
This is a pipeline component that separates the sentences into chunks (e.g. NP, VP).

For now, it uses OpenNLP, but this can be configured to use another chunker.
'''
@Language.factory('chunker', default_config = {'chunker': 'opennlp', 'path' : None})
def create_chunker_component(nlp: Language, name: str, chunker: str, path: str):
    if chunker == 'opennlp':
        return OpenNLPChunkerComponent(nlp, path)

'''
For testing chunks: 
AIM: To perform a systematic review of the efficacy of rabeprazole-based therapies in Helicobacter pylori eradication, and to conduct a meta-analysis comparing the efficacy of rabeprazole and other proton pump inhibitors when co-prescribed with antibiotics.
[Vitamin D: synthesis, metabolism, regulation, and an assessment of its deficiency in patients with chronic renal disease].

Interesting chunks:
Based on these scans, subjects were classified as typical (leftward PT asymmetry) or atypical (rightward PT asymmetry).
OBJECTIVE: To investigate the efficacy of intratympanic dexamethasone injections (IDI) for 15 patients with intractable Meniere's disease (MD).
'''

class OpenNLPChunkerComponent:
    def __init__(self, nlp: Language, path: str):
        self.chunker = OpenNLP(path)

    def __call__(self, doc: Doc) -> Doc:
        for sentence in doc._.sentences:
            opennlp_input = ''
            for word in sentence.words:
               opennlp_input += f'{word.span.text.replace(" ", "__")}_{word.pos_tag} '
            print(opennlp_input)
            chunks = self.chunker.parse(opennlp_input).strip()

            print(f'OpenNLP output: {chunks}')

            current_word_index = 0
            for chunk_token in chunks.split():
                # [ followed by a non-underscore character signifies the start of a new phrase chunk (e.g. NP, VP)
                if len(chunk_token) > 1 and chunk_token[0] == '[' and chunk_token[1] != '_':
                    chunk_type = chunk_token[1:]
                    chunk = Chunk(chunk_type)

                    in_phrase_chunk = True

                # ] signifies the end of a phrase chunk
                elif len(chunk_token) == 1 and chunk_token == ']':
                    chunk.set_chunk_roles()
                    sentence.add_chunk(chunk)

                    in_phrase_chunk = False

                    print(f'Chunk({chunk.chunk_type}): {[word.span.text for word in chunk.words]}')

                # this case shouldn't happen
                elif len(chunk_token) == 1:
                    input(f'Single token (not ]): {chunk_token}')

                else:
                    word_pos = chunk_token.rsplit('_')
                    num_words = len(word_pos[0].split('__'))
                    pos = word_pos[1]

                    words = []
                    for i in range(current_word_index, current_word_index + num_words):
                        words.append(sentence.words[i])

                    if in_phrase_chunk:
                        for i in range(current_word_index, current_word_index + num_words):
                            chunk.words += words

                    else:
                        chunk_type = pos
                        chunk = Chunk(chunk_type)
                        chunk.words = words
                        chunk.set_chunk_roles()
                        sentence.add_chunk(chunk)

                        print(f'Chunk({chunk.chunk_type}): {[word.span.text for word in chunk.words]}')

                    current_word_index += num_words
            if in_phrase_chunk:
                chunk.set_chunk_roles()
                sentence.add_chunk(chunk)

                print(f'Chunk({chunk.chunk_type}): {[word.span.text for word in chunk.words]}')

            # for token in chunks.split():
            #     if len(token) > 1 and token[0] == '[' and token[1] != '_':
            #         start_chunk_index = current_token_index
            #         chunk_type = token[1:]
            #         in_phrase_chunk = True
            #     elif len(token) == 1 and token == ']':
            #         print(f'Chunk: {doc[start_chunk_index: current_token_index]}')
            #         sentence.add_chunk(Chunk(doc[start_chunk_index: current_token_index], chunk_type))
            #         in_phrase_chunk = False
            #         start_chunk_index = None
            #     elif len(token) == 1:
            #         input(f'Single token (not ]): {token}')
            #     else:
            #         if not in_phrase_chunk:
            #             chunk_type = token.rsplit('_')[1]
            #             print(f'Chunk: {doc[current_token_index: current_token_index + 1]}')
            #             sentence.add_chunk(Chunk(doc[current_token_index: current_token_index + 1], chunk_type))
            #         current_token_index += 1
            # if start_chunk_index is not None and start_chunk_index < current_token_index:
            #     print(f'Chunk: {doc[start_chunk_index: current_token_index]}')
            #     sentence.add_chunk(Chunk(doc[start_chunk_index: current_token_index], chunk_type))

        return doc

# '''
# This is a pipeline component that links together words, concepts, and chunks.
# '''
# @Language.factory('harmonizer')
# def create_harmonizer_component(nlp: Language, name: str):
#     Doc.set_extension('words', default = [])
#
#     return HarmonizerComponent(nlp)
#
# # TO DO: add lexicon harmonization
# class HarmonizerComponent:
#     def __init__(self, nlp: Language):
#         pass
#
#     def __call__(self, doc: Doc) -> Doc:
#         print('-----Start: harmonization-----')
#         for sentence in doc._.sentences:
#             for chunk in sentence.chunks:
#                 i = 0
#                 while i < len(chunk.span):
#                     token = chunk.span[i]
#                     if token._.concept_index is None:
#                         concept = None
#                         word = Word(doc[token.i:token.i + 1])
#                     else:
#                         concept = doc._.concepts[token._.concept_index]
#                         word = Word(concept.span)
#
#                     chunk.words.append(Word(word.span, None, concept))
#                     i += len(word.span)
#
#                     print(f'word: {word.span} {word.head} {word.pos_tag}')
#                 chunk.set_chunk_roles()
#
#         print('-----End: harmonization-----')
#
#         return doc

'''
This is a pipeline component that extracts hypernym relations.
'''
@Language.factory('hypernym_analysis')
def create_hypernym_analysis_component(nlp: Language, name: str):
    ## add properties used by SemRep
    Doc.set_extension('relations', default = [])

    return HypernymAnalysisComponent(nlp)

class HypernymAnalysisComponent:
    def __init__(self, nlp: Language):
        self.max_intranp_distance = 5 # make this a parameter

    # def get_concept(self, head, concepts):
    #     for concept in concepts:
    #         if head.text == concept.span.text:
    #             return concept
    #     return None

    def __call__(self, doc: Doc) -> Doc:
        print('-----Start: hypernym analysis-----')

        for sentence in doc._.sentences:
            for i, chunk in enumerate(sentence.chunks):
                # if chunk is a noun phrase
                if chunk.chunk_type == 'NP':
                    self.intraNP_hypernymy(chunk, doc)
                    self.interNP_hypernymy(i, sentence, doc)

        print('-----End: hypernym analysis-----')

        return doc

    def intraNP_hypernymy(self, np_chunk, doc):
        if len(np_chunk.words) == 1:
            return None

        head_concept = np_chunk.words[np_chunk.head_index].associated_concepts

        # identify modifier to the left of head
        modifier_concept = np_chunk.words[np_chunk.head_index - 1].associated_concepts

        self.hypernymy(doc, head_concept, modifier_concept)

        # TO DO: coordination in new code

    def interNP_hypernymy(self, np_chunk_index, sentence, doc):
        np_chunk = sentence.chunks[np_chunk_index]
        np_chunk_head = np_chunk.words[np_chunk.head_index]

        for i in range(np_chunk_index + 1, min(len(sentence.chunks),
                                               np_chunk_index + self.max_intranp_distance)):
            next_chunk = sentence.chunks[i]
            if next_chunk.chunk_type == 'NP':
                next_chunk_head = next_chunk.words[next_chunk.head_index]

                # if next_chunk is not the final chunk, get the chunk after it
                if i + 1 < len(sentence.chunks):
                    after_phrase = doc[sentence.chunks[i + 1].words[0].span.start:sentence.chunks[i + 1].words[-1].span.end + 1].text.strip()
                else:
                    after_phrase = ''

                ip_type = self.get_intervening_phrase_type(np_chunk, next_chunk, after_phrase, doc)

                concept_1 = np_chunk_head.associated_concepts
                concept_2 = next_chunk_head.associated_concepts

                if ip_type == 'APPOS' or ip_type == 'PAREN':
                    self.hypernymy(doc, concept_1, concept_2)
                else:
                    self.hypernymy(doc, concept_1, concept_2, False)

    def hypernymy(self, doc, concept_1, concept_2, both_directions = True):
        # if head has no concept -> no hypernym rel
        if concept_1 is None or concept_2 is None:
            return False

        # if concept is symptoms -> no hypernym rel
        # there are too many false positives
        if concept_2.annotation['MetamapLite'][0]['cui'] in NON_HYPERNYM_CUIS or \
                (both_directions and concept_1.annotation['MetamapLite'][0]['cui'] in NON_HYPERNYM_CUIS):
            return False

        # if modifier and head are the same -> no hypernym rel
        if concept_1.annotation['MetamapLite'][0]['cui'] == concept_2.annotation['MetamapLite'][0]['cui']:
            return False

        # get the common semantic groups of the concepts
        sem_groups = set(concept_1.annotation['MetamapLite'][0]['semgroups']).intersection(set(concept_2.annotation['MetamapLite'][0]['semgroups']))

        # proceed if there are any common sem groups that are not 'anat' or 'conc'
        if len(sem_groups - set(['anat', 'conc'])) == 0:
            return False

        socket_client = SocketClient('ec2-3-144-241-74.us-east-2.compute.amazonaws.com', '12349')
        if socket_client.send(concept_1.annotation['MetamapLite'][0]['cui'] + concept_2.annotation['MetamapLite'][0]['cui'], True) == 'true' and \
                self.allowed_geoa(concept_1, concept_2):
            print(f"Hypernymy: {concept_1.annotation['MetamapLite'][0]['concept_string']} is a {concept_2.annotation['MetamapLite'][0]['concept_string']}")
            doc._.relations.append(Relation(concept_1, 'IS-A', concept_2, 'IS-A'))

            return True
        elif both_directions and socket_client.send(concept_2.annotation['MetamapLite'][0]['cui'] + concept_1.annotation['MetamapLite'][0]['cui'], True) == 'true' and \
                self.allowed_geoa(concept_2, concept_1):
            print(f"Hypernymy: {concept_2.annotation['MetamapLite'][0]['concept_string']} is a {concept_1.annotation['MetamapLite'][0]['concept_string']}")
            doc._.relations.append(Relation(concept_2, 'IS-A', concept_1, 'IS-A'))

            return True

        return False

    def get_intervening_phrase(self, chunk_1, chunk_2, doc):
        return doc[chunk_1.words[-1].span.end:chunk_2.words[0].span.start]

    def get_intervening_phrase_type(self, np_chunk, next_chunk, after_phrase, doc):
        intervening_phrase = self.get_intervening_phrase(np_chunk, next_chunk, doc)

        intervening_phrase_text = intervening_phrase.text.strip()
        # after_phrase_text = after_phrase.text.strip()

        if self.is_appositive(intervening_phrase_text, after_phrase):
            return 'APPOS'
        elif not self.has_balanced_parenthesis(intervening_phrase_text):
            return 'PAREN'
        elif self.contains_copular_verb(intervening_phrase):
            return 'COPULA'
        elif self.contains_other(intervening_phrase, next_chunk):
            return 'OTHER'
        else:
            return None

    def is_appositive(self, intervening_phrase, after_phrase):
        if intervening_phrase == ',' and after_phrase in punctuation:
            return True
        if intervening_phrase in LEFT_PARENTHESES:
            return True
        if intervening_phrase in APPOSITIVE_INDICATORS:
            return True
        return False

    def has_balanced_parenthesis(self, intervening_phrase_text):
        parenthesis = re.sub(r'[^' + ''.join([f'\{p}' for p in LEFT_PARENTHESES + RIGHT_PARENTHESES]) + ']',
                             '', intervening_phrase_text)

        if len(parenthesis) % 2 == 1:
            return False
        else:
            while len(parenthesis) != 0:
                if parenthesis[0] != parenthesis[-1]:
                    return False
                else:
                    parenthesis = parenthesis[1:-1]

        return True

    def contains_copular_verb(self, intervening_phrase):
        copular_verb_index = -1
        for i, token in enumerate(intervening_phrase):
            if token.lemma_ == 'be' and token.tag_.startswith('VB'):
                copular_verb_index = i
                break

        # copular verb not found
        if copular_verb_index == -1:
            return False

        # BE is the only intervening element ??
        if len(intervening_phrase) == copular_verb_index + 1:
            return True

        if len(intervening_phrase) > copular_verb_index + 1:
            # BE not followed by a past-participle
            next_token = intervening_phrase[i + 1]
            if next_token.tag_ != 'VBN':
                return True

            # BE followed by a past-participle and AS
            if len(intervening_phrase) > copular_verb_index + 2:
                next_next_token = intervening_phrase[i + 2]
                if next_next_token.lemma_ != 'as':
                    return True

        for token in intervening_phrase:
            if token.lemma_ == 'remain' and token.tag_.startswith('VB'):
                return True

        return False

    def contains_other(self, intervening_phrase, chunk):
        if len(intervening_phrase) == 0:
            return False

        if len(intervening_phrase) == 1:
            token = intervening_phrase[0]
            if (token.text == 'and' or token.text == 'or') and len(chunk.modifiers) != 0:
                leftmost_modifier =  chunk.modifiers[0]
                if leftmost_modifier[0] == 'other':
                    return True

    def allowed_geoa(self, concept_1, concept_2):
        if 'geoa' in concept_1.annotation['MetamapLite'][0]['semtypes'] and \
                'geoa' in concept_2.annotation['MetamapLite'][0]['semtypes']:
            return concept_2.annotation['MetamapLite'][0]['name'].split()[-1] in GEOA_HYPERNYMS

        return True

'''
This is a pipeline component that extracts other types of relations.
'''
@Language.factory('relational_analysis')
def create_relational_analysis_component(nlp: Language, name: str, ontology_db_path: str, indicators_file_path: str):
    return RelationalAnalysisComponent(nlp, ontology_db_path, indicators_file_path)

class RelationalAnalysisComponent:
    def __init__(self, nlp: Language, ontology_db_path: str, indicators_file_path: str):
        self.ontology_db = []
        with open(ontology_db_path, 'r') as f:
            for line in f:
                line = line.strip().split('|')[1]
                self.ontology_db.append(line)

        self.indicators, self.srindicator_lemmas = parse_semrules_file(indicators_file_path)
        # for indicator in self.srindicators:
        #     print(indicator.string)
        #     print(indicator.lexeme)
        #     print(indicator.verified)
        #     print(indicator.gap_type)
        #     print(indicator.type)
        #     print(indicator.get_most_probable_sense().category)
        #     for sense in indicator.senses:
        #         print(f'\t{sense.category}')
        #         print(f'\t{sense.inverse}')
        #         print(f'\t{sense.cue}')
        #         print(f'\t{sense.negated}')
        #     print()
        # exit()

    def annotate_gapped(self, doc, indicator, window = 2):
        for sentence in doc._.sentences:
            found_first_word = False
            for word in sentence.words:
                # assume a max of 2 lexemes
                # this works for now but double check with java code
                # in particular the sentence window
                # also implement prunespan
                if not found_first_word and word.span.text == indicator.lexeme[0]['lemma']:
                    found_first_word = True
                elif found_first_word and word.span.text == indicator.lexeme[1]['lemma']:
                    if word not in self.annotations:
                        self.annotations[word] = []

                    #make this into a hash
                    found = False
                    for existing_indicator in self.annotations[word]:
                        if existing_indicator == indicator:
                            found = True
                            break

                    if not found:
                        self.annotations[word].append(indicator)

    def annotate_word(self, doc, indicator):
        #for now allow multiple annotations all the times
        self.allow_multiple_annotations = True
        for sentence in doc._.sentences:
            for word in sentence.words:
                #if not allow_multiple_annotations and ...
                # don't use lemma for now
                if word.span.text == indicator.lexeme[0]['lemma'] or word.span.lemma_ == indicator.lexeme[0]['lemma'] : # also need to check pos tag, implement ignorepos
                    # span = word.spans[0]
                    if word not in self.annotations:
                        self.annotations[word] = []

                    #make this into a hash
                    found = False
                    for existing_indicator in self.annotations[word]:
                        if existing_indicator == indicator:
                            found = True
                            break

                    if not found:
                        self.annotations[word].append(indicator)
                # implement posthyphenmatch

    def __call__(self, doc: Doc) -> Doc:
        # might be better to create a separate pipeline component for annotating indicators
        self.annotations = {}
        for indicator in self.indicators:
            # implement ignorePOS
            if indicator.lexeme_type == 'gapped':
                #window of multiple sentences?
                self.annotate_gapped(doc, indicator)
            elif indicator.lexeme_type == 'multiword':
                # self.annotate_multiword(doc, indicator)
                pass
            else:
                self.annotate_word(doc, indicator)

        self.predicates = self.annotations

        # self.predicates = {}
        # for word, indicators in self.annotations.items():
        #     # print(word)
        #     # for indicator in indicators:
        #     #     print(indicator.string)
        #     #new predicate
        #     # self.predicates = []
        #     # for indicator in indicators:
        #     #     self.predicates.append(Predicate(word, indicator))
        #     if word not in self.predicates:
        #         self.predicates[word] = []
        #     for indicator in indicators:
        #         self.predicates[word].append(indicator)
        #      # if ignorePOS:
        #     #     pass

        print('-----Start: relational analysis-----')

        for sentence in doc._.sentences:
            for i, chunk in enumerate(sentence.chunks):
                if chunk.chunk_type == 'NP':
                    self.noun_compound_interpretation(doc, sentence, chunk)

                for word in chunk.words:
                    if word not in self.predicates:
                        continue

                    predicates = self.predicates[word] # or should i just make this a property of words'

                    if chunk.chunk_type == 'VP':
                        self.verbal_interpretation(doc, sentence, predicates, chunk, word)
                    elif chunk.chunk_type == 'ADJP':
                        self.adjectival_interpretation(doc, sentence, predicates, chunk, word)
                    elif chunk.chunk_type == 'PP':
                        self.prepositional_interpretation(doc, sentence, predicates, chunk, word)

                # if (ch.isVP()) verbalInterpretation(css, ch, preds, se, allCandidates);
                # if (ch.isADJP()) adjectivalInterpretation(css, ch, preds, se, allCandidates);
                # if (ch.isPP()) prepositionalInterpretation(css, ch, preds, se, allCandidates);
                # if (ch.isNP()) nominalInterpretation(css, ch, preds, se, allCandidates);

        print('-----End: relational analysis-----')

        return doc

    # def generate_candidates(self, doc):
    #     candidates = []
    #     for word in doc._.chunks:
    #         if word.associated_concepts is not None:
    #             candidates.append(word)
    #
    #     return candidates

    def lookup(self, semtype_1, pred_type, semtype_2):
        return '-'.join([semtype_1, pred_type, semtype_2]) in self.ontology_db

    def verify_and_generate(self, doc, predicates, candidate_pairs, indicator_type):
        if len(candidate_pairs) == 0:
            return None

        # this is for noun compound interpretation
        if predicates is None:
            for modhead in MODHEAD_TYPES:
                inverse = False
                if modhead.startswith('inverse:'):
                    inverse = True
                    modhead = modhead.replace('inverse:', '')
                for candidate_pair in candidate_pairs:
                    if inverse and self.lookup(candidate_pair[1], modhead,
                                          candidate_pair[0]):
                        # self.generate_implicit_relation(doc, modhead, indicator_type,
                        #                         candidate_pair[1],
                        #                         candidate_pair[0])
                        return modhead, inverse
                    elif self.lookup(candidate_pair[0], modhead,
                                          candidate_pair[1]):
                        # self.generate_implicit_relation(doc, modhead, indicator_type,
                        #                                 candidate_pair[0],
                        #                                 candidate_pair[1])
                        return modhead, inverse
        elif indicator_type == 'NOMINAL':
            pass
        else:
            found = False
            for predicate in predicates:
                for sense in predicate.senses:
                    subject_cue = None
                    object_cue = None
                    if sense.cue != '':
                        if '-' in sense.cue:
                            split_cue = sense.cue.split('-')
                            object_cue = split_cue[0]
                            subject_cue = split_cue[1]
                        else:
                            object_cue = sense.cue

                    for candidate_pair in candidate_pairs:
                        for subject_semtype in candidate_pair['subject']['semtypes']:
                            for object_semtype in candidate_pair['object']['semtypes']:
                                if 'subject_cue' in candidate_pair:
                                    subject_cue_lemma = subject_cue
                                else:
                                    subject_cue_lemma = None
                                if 'object_cue' in candidate_pair:
                                    object_cue_lemma = object_cue
                                else:
                                    object_cue_lemma = None

                                if not sense.inverse and \
                                    ((object_cue is None and object_cue_lemma is None) or (object_cue  is not None and object_cue == object_cue_lemma)) and \
                                    self.lookup(subject_semtype, sense.category, object_semtype):
                                    #generate predication
                                    doc._.relations.append(Relation(candidate_pair['subject_span'], sense.category, candidate_pair['object_span'], indicator_type))
                                    return True
                                    found = True
                                    break
                                elif sense.inverse and \
                                    ((object_cue is None and object_cue_lemma is None) or (object_cue  is not None and object_cue == object_cue_lemma)) and \
                                    self.lookup(object_semtype, sense.category, subject_semtype):
                                    doc._.relations.append(Relation(candidate_pair['object_span'], sense.category, candidate_pair['subject_span'], indicator_type))
                                    return True
                                    found = True
                                    break
                    if found: break
                if found: break
            return found

        return None, None

    def generate_implicit_relation(self, doc, modhead, indicator_type, subject, object):
        # print(f"Noun compound: {subject.annotation['MetamapLite'][0]['concept_string']} {modhead} {object.annotation['MetamapLite'][0]['concept_string']}")
        doc._.relations.append(Relation(subject, modhead.upper(), object, indicator_type))

    def noun_compound_interpretation(self, doc, sentence, chunk):
        for i in range(len(chunk.words) - 1, -1, -1):  # in reverse
            word = chunk.words[i]
            if word.chunk_role == 'H' or word.chunk_role == 'M':
                # if not surface_element.is_predicate: # filter the surface elements by predicate
                #     continue

                if word.associated_concepts is None:
                    continue

                right_candidates = word.associated_concepts.annotation['MetamapLite']

                prev_word = chunk.words[i - 1]
                if not prev_word.chunk_role == 'M' or prev_word.associated_concepts is None:
                    continue

                hypenated_adj = False
                left_candidates = []
                # predicates = []
                #
                # if prev_word.tag_ = 'ADJ' and '-' in prev_surface_element.text:
                #     hypenated_adj = True
                #     entity_span = sentence[prev_surface_element:surface_element.indexof('-')]
                #     predicate_span = sentence[surface_element.indexof('-'):prev_surface_element.endspan]
                #
                #     temp_candidates = candidates.get(prev)
                #     if len(temp_candidates) > 0:
                #         for candidate in temp_candidates:
                #             pass
                #             # check subsume function
                #             # if (SpanList.subsume(entsp, c.getEntity().getSpan())) {
                #             # leftCands.add(c);
                #             # }
                #
                #         preds = prev.filter_by_predicates
                #         for pred in preds:
                #             pass
                #             # if (SpanList.subsume(prsp, sem.getSpan())) preds.add(sem);
                # else


                left_candidates = prev_word.associated_concepts.annotation['MetamapLite']

                # CandidatePair.generateCandidatePairs(leftCands, rightCands)
                candidate_pairs = []
                for subj in left_candidates:
                    for obj in right_candidates:
                        candidate_pairs.append([subj['semtypes'][0], obj['semtypes'][0]])

                    # if hypenated_adj:
                    #     found = verifyAndGenerate(doc, sent, preds, pairs, IndicatorType.ADJECTIVE)
                    # else:

                modhead, inverse = self.verify_and_generate(doc, None, candidate_pairs, 'MODHEAD')
                if modhead is not None:
                    if inverse:
                        self.generate_implicit_relation(doc, modhead, None,
                                                        word.associated_concepts,
                                                        prev_word.associated_concepts)
                    else:
                        self.generate_implicit_relation(doc, modhead, None,
                                                        prev_word.associated_concepts,
                                                        word.associated_concepts)
                    return None

        modifiers = []
        for modifier in modifiers:
            for surface_element in modifier:
                # if surface_element.is_adjectival:
                #     continue
                # surface_element.filter_by_predicates
                # if pred.size == 0:
                #     continue

                next = surface_element[i + 1]
                prev = getprevsurfaceelement[i - 1]

                right_candidates = candidates.get(next)
                left_candidates = candidatess.get(left)

                # CandidatePair.generateCandidatePairs(leftCands, rightCands)
                if right_candidates is None or left_candidates is None:
                    break

                candidate_pairs = []
                for subj in right_candidates:
                    for obj in left_candidates:
                        candidate_pairs.append([subj, obj])

                found = self.verify_and_generate(doc, predicates, candidate_pairs, 'ADJECTIVE')

    def verbal_interpretation(self, doc, sentence, predicates, chunk, word):
        print('verbal interpretation')
        passive = False
        if chunk.is_in_passive_voice(sentence):
            passive = True

        #previousNP
        current_chunk = chunk
        while True:
            prev = sentence.get_previous_chunk(current_chunk)
            if prev is None:
                return None
            if prev.chunk_type == 'NP':
                break
            current_chunk = prev

        #nextCuedNP
        current_chunk = chunk
        while True:
            next = sentence.get_next_chunk(current_chunk)
            if next is None:
                return None
            if next.chunk_type == 'NP':
                for word in next.words:
                    found_entity = False
                    if word.is_entity:
                        found_entity = True
                        break
                if found_entity:
                    break
            current_chunk = next

        found = False
        cue = None
        while next is not None:
            word = next.words[next.head_index]

            # if cue is None:
            #     cue_head = None
            # else:
            #     cue_head..
            # #cuehead
            # # cue = next.get_cue()
            # # if cue is not None:
            # #     cue_head = cue.get_head()
            # # else:
            # #     cue_head = None

            right_candidates = word.associated_concepts.annotation['MetamapLite']

            while prev is not None and prev.words[prev.head_index].associated_concepts is not None:
                left_candidates = prev.words[prev.head_index].associated_concepts.annotation['MetamapLite']
                if not passive:
                    candidate_pairs = []
                    for subj in left_candidates:
                        for obj in right_candidates:
                            candidate_pairs.append({'subject' : subj,
                                                    'subject_span' : prev.words[prev.head_index].associated_concepts,
                                                    'subject_cue' : None,
                                                    'object' : obj,
                                                    'object_span': word.associated_concepts,
                                                    'object_cue' : None})
                else:
                    candidate_pairs = []
                    for subj in right_candidates:
                        for obj in left_candidates:
                            candidate_pairs.append({'subject': subj,
                                                    'subject_span': word.associated_concepts,
                                                    'subject_cue': None,
                                                    'object': obj,
                                                    'object_span': prev.words[
                                                        prev.head_index].associated_concepts,
                                                    'object_cue': None})

                found = self.verify_and_generate(doc, predicates, candidate_pairs, 'VERB')

                if found:
                    break
                current_chunk = prev
                while True:
                    prev = sentence.get_previous_chunk(current_chunk)
                    if prev is None:
                        return None
                    if prev.chunk_type == 'NP':
                        break
                    current_chunk = prev

            if found:
                return None

            current_chunk = next
            while True:
                next = sentence.get_next_chunk(current_chunk)
                if next is None:
                    return None
                if next.chunk_type == 'NP':
                    for word in next.words:
                        found_entity = False
                        if word.is_entity:
                            found_entity = True
                            break
                    if found_entity:
                        break
                current_chunk = next

            current_chunk = chunk
            while True:
                prev = sentence.get_previous_chunk(current_chunk)
                if prev is None:
                    return None
                if prev.chunk_type == 'NP':
                    break
                current_chunk = prev

    def adjectival_interpretation(self, doc, sentence, predicates, chunk, word):
        print('adjectival interpretation')

        #previousNP
        current_chunk = chunk
        while True:
            prev = sentence.get_previous_chunk(current_chunk)
            if prev is None:
                return None
            if prev.chunk_type == 'NP':
                break
            current_chunk = prev

        #nextCuedNP
        current_chunk = chunk
        while True:
            next = sentence.get_next_chunk(current_chunk)
            if next is None:
                return None
            if next.chunk_type == 'NP':
                for word in next.words:
                    found_entity = False
                    if word.is_entity:
                        found_entity = True
                        break
                if found_entity:
                    break
            current_chunk = next

        found = False
        cue = None
        while next is not None:
            word = next.words[next.head_index]

            # if cue is None:
            #     cue_head = None
            # else:
            #     cue_head..
            # #cuehead
            # # cue = next.get_cue()
            # # if cue is not None:
            # #     cue_head = cue.get_head()
            # # else:
            # #     cue_head = None

            right_candidates = word.associated_concepts.annotation['MetamapLite']

            while prev is not None and prev.words[prev.head_index].associated_concepts is not None:
                left_candidates = prev.words[prev.head_index].associated_concepts.annotation['MetamapLite']
                candidate_pairs = []
                for subj in left_candidates:
                    for obj in right_candidates:
                        candidate_pairs.append({'subject' : subj,
                                                'subject_span' : prev.words[prev.head_index].associated_concepts,
                                                'subject_cue' : None,
                                                'object' : obj,
                                                'object_span': word.associated_concepts,
                                                'object_cue' : None})

                found = self.verify_and_generate(doc, predicates, candidate_pairs, 'ADJECTIVE')

                if found:
                    break
                current_chunk = prev
                while True:
                    prev = sentence.get_previous_chunk(current_chunk)
                    if prev is None:
                        return None
                    if prev.chunk_type == 'NP':
                        break
                    current_chunk = prev

            if found:
                return None

            current_chunk = next
            while True:
                next = sentence.get_next_chunk(current_chunk)
                print(next.sentence_index)
                if next is None:
                    return None
                if next.chunk_type == 'NP':
                    for word in next.words:
                        found_entity = False
                        if word.is_entity:
                            found_entity = True
                            break
                    if found_entity:
                        break
                current_chunk = next

            current_chunk = chunk
            while True:
                prev = sentence.get_previous_chunk(current_chunk)
                if prev is None:
                    return None
                if prev.chunk_type == 'NP':
                    break
                current_chunk = prev

    def prepositional_interpretation(self, doc, sentence, predicates, chunk, word):
        print('prepositional interpretation')

        # nextNP
        current_chunk = chunk
        while True:
            right = sentence.get_next_chunk(current_chunk)
            if right is None:
                return None
            if right.chunk_type == 'NP':
                break
            current_chunk = right

        # previousNP
        current_chunk = chunk
        while True:
            left = sentence.get_previous_chunk(current_chunk)
            if left is None:
                return None
            if left.chunk_type == 'NP':
                break
            current_chunk = left

        found = False
        while left is not None:
            word = right.words[right.head_index]

            right_candidates = word.associated_concepts.annotation['MetamapLite']
            left_candidates = left.words[left.head_index].associated_concepts.annotation['MetamapLite']
            candidate_pairs = []
            for subj in left_candidates:
                for obj in right_candidates:
                    candidate_pairs.append({'subject': subj,
                                            'subject_span': left.words[left.head_index].associated_concepts,
                                            'subject_cue': None,
                                            'object': obj,
                                            'object_span': word.associated_concepts,
                                            'object_cue': None})

            found = self.verify_and_generate(doc, predicates, candidate_pairs, 'PREPOSITION')

            if found:
                return None

            current_chunk = left
            while True:
                left = sentence.get_previous_chunk(current_chunk)
                if left is None:
                    return None
                if left.chunk_type == 'NP':
                    break
                current_chunk = left


    def nominal_interpretation(self, doc, sentence, predicates, chunk, word):
        print('nominal interpretation')

        right_arg = False

        complements = get_nominal_complements(word)
        # nextNP
        current_chunk = chunk
        while True:
            right = sentence.get_next_chunk(current_chunk)
            if right is None:
                return None
            if right.chunk_type == 'NP':
                break
            current_chunk = right

        # if current_chunk is not None:
        #     right_cue = current_chunk.cue
        #

        found = False
        if right_arg:
            # // [NOM][PREP SUBJ] [PREP OBJ]
            # // [NOM][PREP OBJ] [PREP SUBJ]
            # // [NOM][PREP OBJ] ([SUBJ]) // This does not work, need to modify chunks
            # // [NOM][PREP OBJ], SUBJ,
            # // [NOM][PREP OBJ] [BE SUBJ]

            # nextCuedNP
            right2 = chunk
            while True:
                next = sentence.get_next_chunk(current_chunk)
                if next is None:
                    return None
                if next.chunk_type == 'NP':
                    for word in next.words:
                        found_entity = False
                        if word.is_entity:
                            found_entity = True
                            break
                    if found_entity:
                        break
                right2 = next

            while right2 is not None:
                found = self.verify_and_generate(doc, None, candidate_pairs, 'NOMINAL')
                if found:
                    break

            # // [SUBJ NOM][PREP OBJ]
            # // [OBJ NOM][PREP SUBJ]
            if not found:
                for i in range(len(chunk.modifiers) - 1, -1, -1):
                    re1role = nominal_candidate_role(right1cue.head, null, lex_complements)
                    if re1role == 'S':
                        pairs = generate_candidate_pairs(right1cands, right1h, right1t,
                                                         se_cands, None, None)
                    else:
                        pairs = generate_candidate_pairs(se_cands, None, None,
                                                         right1cands, right1h, right1t)
                    found = self.verify_and_generate(doc, None, pairs, 'NOMINAL')
                    if found:
                        break

            # // [SUBJ][PREP NOM] [PREP OBJ]
            if not found:
                for i in range(len(chunk.modifiers) - 1, -1, -1):
                    re1role = nominal_candidate_role(right1cue.head, null, lex_complements)
                    if re1role == 'S':
                        pairs = generate_candidate_pairs(right1cands, right1h, right1t,
                                                         se_cands, None, None)
                    else:
                        pairs = generate_candidate_pairs(se_cands, None, None,
                                                         right1cands, right1h, right1t)
                    found = self.verify_and_generate(doc, None, pairs, 'NOMINAL')
                    if found:
                        break

    def nominal_candidate_role(self, word1, word2, lex_complements):
        if word1 in NOMINAL_SUBJECT_CUES:
            return 'S'
        elif word2 is None or word2 in NOMINAL_SUBJECT_CUES:
            return 'O'
        elif word1 in NOMINAL_OBJECT_CUES and word2 in lex_complements:
            return 'S'
        return 'O'
