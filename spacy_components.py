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

PREDICATIVE_CATEGORIES = set(['NN', 'VB', 'JJ', 'RB', 'PR'])
HEAD_CATEGORIES = set(['IN', 'WD', 'WP', 'WR'])

LEFT_PARENTHESES = ['(', '{', '[']
RIGHT_PARENTHESES = [')', '}', ']']
APPOSITIVE_INDICATORS = ['such as', 'particularly', 'in particular', 'including']

NON_HYPERNYM_CUIS = ['C1457887'] # Symptom
GEOA_HYPERNYMS = ['country', 'countries', 'islands', 'continent', 'locations', 'city', 'cities']

MODHEAD_TYPES = ['process_of', 'inverse:uses', 'location_of', 'inverse:part_of', 'inverse:process_of']

def get_pos_category(tag):
    return tag[:2]

class Sentence:
    def __init__(self):
        self.chunks = []

    def add_chunk(self, chunk):
        self.chunks.append(chunk)

class Chunk:
    def __init__(self, span, chunk_type):
        self.span = span
        self.chunk_type = chunk_type
        self.head_index = None
        self.modifiers = []
        self.words = []

    # @property
    # def candidates(self):
    #     return [word for word in self.words if word.associated_concept is not None]

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

class Word:
    def __init__(self, spans, chunk_role = None, associated_concept = None):
        # span is a list of spans, for flexibility, i.e., in case of gapped words
        self.span = spans
        self.chunk_role = chunk_role
        self.associated_concept = associated_concept

        self.set_head()
        self.set_pos_tag()

    def set_pos_tag(self):
        self.pos_tag = self.head.tag_

    def is_entity(self):
        return self.associated_concept is None

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
    def __init__(self, subject, predicate, object):
        self.subject = subject
        self.predicate = predicate
        self.object = object

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

        print('-----End: lexicon matching-----')

        return doc

'''
This is a pipeline component that separates the sentences into chunks (e.g. NP, VP).

For now, it uses OpenNLP, but this can be configured to use another chunker.
'''
@Language.factory('chunker', default_config = {'chunker': 'opennlp', 'path' : None})
def create_chunker_component(nlp: Language, name: str, chunker: str, path: str):
    ## add properties used by SemRep
    Doc.set_extension('sentences', default = [])

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
        current_token_index = 0
        for sent in doc.sents:
            opennlp_input = ''
            for token in sent:
               opennlp_input += f'{token.text}_{token.tag_} '
            chunks = self.chunker.parse(opennlp_input).strip()

            print(f'OpenNLP output: {chunks}')

            sentence = Sentence()

            for token in chunks.split():
                if len(token) > 1 and token[0] == '[' and token[1] != '_':
                    start_chunk_index = current_token_index
                    chunk_type = token[1:]
                    in_phrase_chunk = True
                elif len(token) == 1 and token == ']':
                    print(f'Chunk: {doc[start_chunk_index: current_token_index]}')
                    sentence.add_chunk(Chunk(doc[start_chunk_index: current_token_index], chunk_type))
                    in_phrase_chunk = False
                elif len(token) == 1:
                    input(f'Single token (not ]): {token}')
                else:
                    if not in_phrase_chunk:
                        chunk_type = token.rsplit('_')[1]
                        print(f'Chunk: {doc[current_token_index: current_token_index + 1]}')
                        sentence.add_chunk(Chunk(doc[current_token_index: current_token_index + 1], chunk_type))
                    current_token_index += 1
            if start_chunk_index < current_token_index:
                print(f'Chunk: {doc[start_chunk_index: current_token_index]}')
                sentence.add_chunk(Chunk(doc[start_chunk_index: current_token_index], chunk_type))

            # OLD CHUNKING CODE

            # This code does not work for this type of text, need to fix:
            # Hypertension patients take[aspirin]].
            # But for now, it works on most texts.

            # # (?=(\[.*?\]))|(?=(\].*?\[)|(._\.)) --> old regex
            # # current one fixes issues when text has brackets
            # # use this for testing: [Vitamin D: synthesis, metabolism, regulation, and an assessment of its deficiency in patients with chronic renal disease].
            # for chunk in re.findall(r'(?=(\[(?!_).*?\](?!_)))|(?=(\].*?\[)|([\.:]_[\.\:]))', chunks):
            #     # if actual chunk, e.g. [NP Analgesic_JJ aspirin_NN]
            #     if len(chunk[0]) > 0:
            #         chunk = chunk[0].strip()[1:-1].split()
            #
            #         chunk_type = chunk[0]
            #         chunk_tokens = chunk[1:]
            #
            #         end_index = cur_token_index + len(chunk_tokens)
            #         sentence.add_chunk(Chunk(doc[cur_token_index: end_index], chunk_type))
            #
            #         print(f'Chunk: {sentence.chunks[-1].span}')
            #
            #         cur_token_index = end_index
            #
            #     # if space between chunks, i.e. ] [
            #     # need example for this case
            #     elif len(chunk[1]) > 0:
            #         chunk = chunk[1][1:-1].strip()
            #         if len(chunk) > 0:
            #             for chunk in chunk.split():
            #                 end_index = cur_token_index + 1
            #
            #                 sentence.add_chunk(Chunk(doc[cur_token_index: end_index], doc[cur_token_index: end_index].text))
            #
            #                 print(f'Chunk: {sentence.chunks[-1].span}')
            #
            #                 cur_token_index = end_index
            #
            #         # cur_token_index + len(chunk.split())
            #
            #     elif len(chunk[2]) > 0:
            #         end_index = cur_token_index + 1
            #         sentence.add_chunk(Chunk(doc[cur_token_index: end_index], doc[cur_token_index: end_index].text))
            #
            #         print(f'Chunk: {sentence.chunks[-1].span}')
            #
            #         cur_token_index = end_index

            doc._.sentences.append(sentence)

        return doc

'''
This is a pipeline component that links together words, concepts, and chunks.
'''
@Language.factory('harmonizer')
def create_harmonizer_component(nlp: Language, name: str):
    Doc.set_extension('words', default = [])

    return HarmonizerComponent(nlp)

# TO DO: add lexicon harmonization
class HarmonizerComponent:
    def __init__(self, nlp: Language):
        pass

    def __call__(self, doc: Doc) -> Doc:
        print('-----Start: harmonization-----')
        for sentence in doc._.sentences:
            for chunk in sentence.chunks:
                i = 0
                while i < len(chunk.span):
                    token = chunk.span[i]
                    if token._.concept_index is None:
                        concept = None
                        word = Word(doc[token.i:token.i + 1])
                    else:
                        concept = doc._.concepts[token._.concept_index]
                        word = Word(concept.span)

                    chunk.words.append(Word(word.span, None, concept))
                    i += len(word.span)

                    print(f'word: {word.span} {word.head} {word.pos_tag}')
                chunk.set_chunk_roles()

        print('-----End: harmonization-----')

        return doc

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
        if len(np_chunk.span) == 1:
            return None

        head_concept = np_chunk.words[np_chunk.head_index].associated_concept

        # identify modifier to the left of head
        modifier_concept = np_chunk.words[np_chunk.head_index - 1].associated_concept

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
                    after_phrase = sentence.chunks[i + 1].span.text.strip()
                else:
                    after_phrase = ''

                ip_type = self.get_intervening_phrase_type(np_chunk, next_chunk, after_phrase, doc)

                concept_1 = np_chunk_head.associated_concept
                concept_2 = next_chunk_head.associated_concept

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
            doc._.relations.append(Relation(concept_1, 'IS-A', concept_2))

            return True
        elif both_directions and socket_client.send(concept_2.annotation['MetamapLite'][0]['cui'] + concept_1.annotation['MetamapLite'][0]['cui'], True) == 'true' and \
                self.allowed_geoa(concept_2, concept_1):
            print(f"Hypernymy: {concept_2.annotation['MetamapLite'][0]['concept_string']} is a {concept_1.annotation['MetamapLite'][0]['concept_string']}")
            doc._.relations.append(Relation(concept_2, 'IS-A', concept_1))

            return True

        return False

    def get_intervening_phrase(self, chunk_1, chunk_2, doc):
        return doc[chunk_1.span[-1].i + 1:chunk_2.span[0].i]

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
def create_relational_analysis_component(nlp: Language, name: str, ontology_db_path: str):
    return RelationalAnalysisComponent(nlp, ontology_db_path)

class RelationalAnalysisComponent:
    def __init__(self, nlp: Language, ontology_db_path: str):
        self.ontology_db = []
        with open(ontology_db_path, 'r') as f:
            for line in f:
                line = line.strip().split('|')[1]
                self.ontology_db.append(line)

    def __call__(self, doc: Doc) -> Doc:
        print('-----Start: relational analysis-----')

        for sentence in doc._.sentences:
            for i, chunk in enumerate(sentence.chunks):
                if chunk.chunk_type == 'NP':
                    self.noun_compound_interpretation(doc, sentence, chunk)

        print('-----End: relational analysis-----')

        return doc

    # def generate_candidates(self, doc):
    #     candidates = []
    #     for word in doc._.chunks:
    #         if word.associated_concept is not None:
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
        return None, None

    def generate_implicit_relation(self, doc, modhead, indicator_type, subject, object):
        print(f"Noun compound: {subject.annotation['MetamapLite'][0]['concept_string']} {modhead} {object.annotation['MetamapLite'][0]['concept_string']}")
        doc._.relations.append(Relation(subject, modhead.upper(), object))

    def noun_compound_interpretation(self, doc, sentence, chunk):
        for i in range(len(chunk.words) - 1, -1, -1):  # in reverse
            word = chunk.words[i]
            if word.chunk_role == 'H' or word.chunk_role == 'M':
                # if not surface_element.is_predicate: # filter the surface elements by predicate
                #     continue

                if word.associated_concept is None:
                    continue

                right_candidates = word.associated_concept.annotation['MetamapLite']

                prev_word = chunk.words[i - 1]
                if not prev_word.chunk_role == 'M' or prev_word.associated_concept is None:
                    continue

                hypenated_adj = False
                left_candidates = []
                # predicates = []

                # if prev_surface_element.isadjectival and '-' in prev_surface_element.text:
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


                left_candidates = prev_word.associated_concept.annotation['MetamapLite']

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
                                                        word.associated_concept,
                                                        prev_word.associated_concept)
                    else:
                        self.generate_implicit_relation(doc, modhead, None,
                                                        prev_word.associated_concept,
                                                        word.associated_concept)
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


