import argparse
import errno
import os
import sys
import re

import configparser

import json

from medline import *
from string import punctuation

sys.path.append('biopreproc')
sys.path.append('server')
from sentence_splitter import *
from socketclient import *
from serverproxyclient import *
from srindicator import *
from spacy_components import *

import spacy

import logging
logging.basicConfig(filename='semrep.log',filemode='a', level=logging.INFO)
def print2log(s):
    logging.info(s)
    print(s)
#in other files, just:
#from log2 import print2log

PREDICATIVE_CATEGORIES = set(['NN', 'VB', 'JJ', 'RB', 'PR'])

# create a SemRep class


def get_head_index(np_chunk):
    return len(np_chunk) - 1

def get_concept(term, concepts):
    if (term.idx, term.idx + len(term)) in concepts:
        return concepts[(term.idx, term.idx + len(term))]
    else:
        return None

#hierarchy: first mention (e.g. GNormPlus over MetamapLite)
def referential_analysis(text, ontologies = [GNormPlus, MetamapLite]):
    #import json
    processes = {}
    with Pool(processes = len(ontologies)) as pool:
        for ontology in ontologies:
            processes[ontology.__name__] = pool.apply_async(ontology(servers['host'],
                                             servers[ontology.__name__.lower() + '_port']).annotate, args = (text,))

        annotations = {}
        for ontology in ontologies:
            annotations[ontology.__name__] = processes[ontology.__name__].get()

    # wsd -> THIS DOES NOT WORK AGAIN -- NEED TO RECHECK
    # WSD(servers['host'], servers[ontology.__name__.lower() + '_port']).disambiguate(annotations['MetamapLite'], text)

    span_lengths = {}
    for ontology in ontologies:
        for (start, length), concept in annotations[ontology.__name__].items():
            if length not in span_lengths:
                span_lengths[length]  = {}
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
                    print2log(f'DONT ADD: {(start, end)}')
                    merge = False
                    break
            if merge:
                merged_annotations[(start, end)] = concept
                t_annotations[f't{start}_{end}'] = concept

    with open("an.tmp", 'a') as f:
        f.write(json.dumps(t_annotations,indent=2)) #error, have2change
        f.write('\n')

    return merged_annotations

def hypernym_analysis(spacy_sent, np_chunks, concepts):
    for np_chunk in np_chunks:
        intraNP_hypernymy(np_chunk, concepts)
    interNP_hypernymy(spacy_sent, np_chunks, concepts)

def intraNP_hypernymy(np_chunk, concepts):
    if len(np_chunk) == 1:
        return None

    # identify head and check associated concept
    head_index = get_head_index(np_chunk)
    head = np_chunk[head_index]

    head_concept  = get_concept(head, concepts)

    # if head has no concept -> no hypernym rel
    if head_concept is None:
        return None

    # if concept is symptoms -> no hypernym rel
    # there are too many false positives
    if head_concept['cui'] == 'C1457887':
        return None

    # identify modifier to the left of head
    modifier = np_chunk[head_index - 1]
    modifier_concept = get_concept(modifier, concepts)

    # if modifier has no concept -> no hypernym rel
    if modifier_concept is None:
        return None

    # if modifier and head are the same -> no hypernym rel
    if head_concept['cui'] == modifier_concept['cui']:
        return None
    else:
        # check for possible hypernymy
        return hypernymy(head_concept, modifier_concept)

def interNP_hypernymy(spacy_sent, np_chunks, concepts, max_distance = 5):
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
                ip_type = get_intervening_phrase_type(spacy_sent[np_chunks[i][-1].i + 1:np_chunks[j][0].i].text.strip(),
                                                      spacy_sent[np_chunks[j][-1].i + 1].text)
            else:
                ip_type = get_intervening_phrase_type(spacy_sent[np_chunks[i][-1].i + 1:np_chunks[j][0].i].text.strip(),
                                                      '')

            if ip_type == 'APPOS' or ip_type == 'PAREN':
                hypernymy(head_concept, modifier_concept)
            else:
                hypernymy(head_concept, modifier_concept, False)

def hypernymy(concept_1, concept_2, both_directions = True):
    # get the common semantic groups of the concepts
    sem_groups = set(concept_1['semgroups']).intersection(set(concept_2['semgroups']))

    # proceed if there are any common sem groups that are not 'anat' or 'conc'
    if len(sem_groups - set(['anat', 'conc'])) == 0:
        return None

    socket_client = SocketClient(HOST, HIERARCHY_PORT)
    if socket_client.send(concept_1['cui'] + concept_2['cui'], True) == 'true':
        print2log(f"{concept_1['concept_string']} is a {concept_2['concept_string']}")
    elif both_directions and socket_client.send(concept_2['cui'] + concept_1['cui'], True) == 'true':
        print2log(f"{concept_2['concept_string']} is a {concept_1['concept_string']}")

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
    parenthesis = re.sub(r'[^' + ''.join( [f'\{p}' for p in LEFT_PARENTHESES + RIGHT_PARENTHESES]) +']', '', intervening_phrase)

    if len(parenthesis) % 2 == 1:
        return False
    else:
        while len(parenthesis) != 0:
            if parenthesis[0] != parenthesis[-1]:
                return False
            else:
                parenthesis = parenthesis[1:-1]

    return True

NOMINAL_SUBJECT_CUES = ["by","with","via"]
NOMINAL_OBJECT_CUES = ['of']

def relational_analysis(sentence):
    candidates = generate_candidates(sentence)
    for chunk in chunks:
        if chunk.is_np:
            noun_compound_interpretation(sentence, chunk, candidates)

        for surface_element in chunks.surface_elements:
            if surface_element.is_predicate:
                if chunk.isVP():
                    verbal_interpretation(css, ch, preds, se, allCandidates)
                if chunk.isADJP():
                    adjectival_interpretation(css, ch, preds, se, allCandidates)
                if chunk.isPP():
                    prepositional_interpretation(css, ch, preds, se, allCandidates)
                if chunk.isNP():
                    nominal_interpretation(css, ch, preds, se, allCandidates)


def generate_candidates(surface_elements):
    candidates = []
    for surface_elements in surface_elements:
        if surface_elements.is_entity:
            for concept in surface_elements.entity.get_concepts():
                candidates.append({'entity' : surface_elements.entity,
                                   'concept' : concept,
                                   'semtype' : concept.semtype})
    return candidates

#@cache
import functools
@functools.lru_cache(maxsize=None)
def lookup(semtype_1, pred_type, semtype_2):
    return '-'.join([semtype_1, pred_type, semtype_2]) in ontology_db

def noun_compound_interpretation(sentence, chunk, candidates):
    for surface_element in chunk.surface_elements: # in reverse
        if chunk.is_head_of(surface_element) or chunk.is_modifier_of(surface_element):
            if not surface_element.is_predicate: # filter the surface elements by predicate
                continue

            right_candidates = candidates.get(surface_element) # get the candidates for this surface element

            prev_surface_element = get_prev_surface_element()

            hypenated_adj = False
            left_candidates = []
            predicates = []

            if prev_surface_element.isadjectival and '-' in prev_surface_element.text:
                hypenated_adj = True
                entity_span = sentence[prev_surface_element:surface_element.indexof('-')]
                predicate_span = sentence[surface_element.indexof('-'):prev_surface_element.endspan]

                temp_candidates = candidates.get(prev)
                if len(temp_candidates) > 0:
                    for candidate in temp_candidates:
                        pass
                        # check subsume function
                        # if (SpanList.subsume(entsp, c.getEntity().getSpan())) {
                        # leftCands.add(c);
                        # }

                    preds = prev.filter_by_predicates
                    for pred in preds:
                        pass
                        # if (SpanList.subsume(prsp, sem.getSpan())) preds.add(sem);
                else:
                    if candidates.get(prev) is not None:
                        left_candidates = candidates.get(prev)
                CandidatePair.generateCandidatePairs(leftCands, rightCands)

                if hypenated_adj:
                    found = verifyAndGenerate(doc, sent, preds, pairs, IndicatorType.ADJECTIVE)
                else:
                    found = verifyAndGenerate(doc, sent, null, pairs, IndicatorType.MODHEAD)

    for modifier in chunk.get_modifiers():
        for surface_element in modifier:
            if surface_element.is_adjectival:
                continue
            surface_element.filter_by_predicates
            if pred.size == 0:
                continue

            next = getnextsurfaceelemenet
            prev = getprevsurfaceelement

            right_candidates = candidates.get(next)
            left_candidates = candidatess.get(left)

            if right_candidates is None or left_candidates is None:
                break

            CandidatePair.generateCandidatePairs(leftCands, rightCands)
            found = verifyAndGenerate(doc,sent,preds,pairs,IndicatorType.ADJECTIVE)

def verbal_interpretation(sentence, chunk, preds):
    passive = False
    if chunk.is_passive_voice():
        passive = True

    prev = get_prev_chunk(chunk)
    next = get_next_chunk(chunk)

    found = False
    while next is not None:
        nh = next.get_chunk().get_head()
        cue = next.get_cue()
        if cue is not None:
            cue_head = cue.get_head()
        else:
            cue_head = None

        right_candidates = candidates.get(nh)
        while prev is not None:
            left_candidates = candidates.get(prev.gethead())
            if not passive:
                pairs = CandidatePair.generateCandidatePairs(leftCands)
            else:
                pairs = CandidatePair.generateCandidatePairs(rightCands)

            found = verify_and_generate(doc,sent,preds,pairs,IndicatorType.VERB)

            if found:
                break
                prev = sent.prev_np(prev)

        if found:
            return None
        next = sent.nextcuednp
        prev = sent.nextcuednp

def adjectival_interpretation(sentence, chunk, preds):
    passive = False
    if chunk.is_passive_voice():
        passive = True

    prev = get_prev_chunk(chunk)
    next = get_next_chunk(chunk)

    found = False
    while next is not None:
        nh = next.get_chunk().get_head()
        cue = next.get_cue()
        if cue is not None:
            cue_head = cue.get_head()
        else:
            cue_head = None

        right_candidates = candidates.get(nh)
        while prev is not None:
            left_candidates = candidates.get(prev.gethead())
            if not passive:
                pairs = CandidatePair.generateCandidatePairs(leftCands)
            else:
                pairs = CandidatePair.generateCandidatePairs(rightCands)

            found = verify_and_generate(doc, sent, preds, pairs, IndicatorType.VERB)

            if found:
                break
                prev = sent.prev_np(prev)

        if found:
            return None
        next = sent.nextcuednp
        prev = sent.nextcuednp

def prepositional_interpretation():
    passive = False
    if chunk.is_passive_voice():
        passive = True

    prev = get_prev_chunk(chunk)
    next = get_next_chunk(chunk)

    found = False
    while next is not None:
        nh = next.get_chunk().get_head()
        cue = next.get_cue()
        if cue is not None:
            cue_head = cue.get_head()
        else:
            cue_head = None

        right_candidates = candidates.get(nh)
        while prev is not None:
            left_candidates = candidates.get(prev.gethead())
            if not passive:
                pairs = CandidatePair.generateCandidatePairs(leftCands)
            else:
                pairs = CandidatePair.generateCandidatePairs(rightCands)

            found = verify_and_generate(doc, sent, preds, pairs, IndicatorType.VERB)

            if found:
                break
                prev = sent.prev_np(prev)

        if found:
            return None
        next = sent.nextcuednp
        prev = sent.nextcuednp

def nominal_interpretation():
    pass

def verify_and_generate():
    pass

def process_text(text):
    """Processes a single text document

    Args:
        text (str): document to process

    Returns:
        output: triples extracted using SemRep
    """
    if text is None:
        return None

    print2log(f'Processing: {text}')
    doc = spacynlp(text)
    # for lm in doc._.relations:
    # for lm in doc._.concepts:
    #     print(lm.span)
    #     print(lm.annotation)
    print2log(f'len:text:{len(text)},doc:{len(doc)}')
    print2log('-' * 50)

    sentences = []
    # for sentence in doc.sents:
    #     print(f'Processing sentence: {sentence}')
        # sentence = Sentence(config)
        # sentence.spacy = spacynlp(sentence_text)
        # sentence.surface_elements = lexaccess.get_matches(sentence.spacy)
        # sentence.indicators = annotate_indicators(sentence.spacy, srindicators_list, srindicator_lemmas)
        #
        # concepts = referential_analysis(text)
#<<<<<<< Updated upstream

        # change noun chunks to return list instead of generator
        # for n in sentence.spacy.noun_chunks: print(n)
#       hypernym_analysis(sentence.spacy, concepts)

        #print(concepts)
        # print(f'concepts:{concepts}')
        #with open("an.tmp", 'a') as f:
        #    f.write(concepts) #error, have2change
        #    f.write('\n')
    # print('DONE')
        #relational_analysis(sentence.surface_elements)


def setup_nlp_config(nlp_config):
    """Load NLP preprocessing libraries with the specified configurations

    Args:
        nlp_config (dict or configparser.SectionProxy): configuration settings
    """
    global spacynlp
    spacynlp = spacy.load(nlp_config['spacy'])
    spacynlp.add_pipe('lexmatcher', after='parser',
                      config={'path': nlp_config['lexaccess_path']})
    spacynlp.add_pipe('concept_match', after = 'lexmatcher',
                      config = {'ontologies' : nlp_config['ontologies'], 'server_paths' : servers})
    spacynlp.add_pipe('chunker', after = 'concept_match',
                      config = {'path' : nlp_config['chunker_path']})
    spacynlp.add_pipe('harmonizer', after='chunker')
    spacynlp.add_pipe('hypernym_analysis', after='harmonizer')
    #
    # log the pipeline?
    print2log(spacynlp.pipe_names)

def setup_semrep_config(semrep_config):
    """Load SemRep rules and databases

    Args:
        semrep_config (dict or configparser.SectionProxy): file paths of rules/databases
    """
    global srindicators_list
    global srindicator_lemmas
    srindicators_list, srindicator_lemmas = parse_semrules_file(semrep_config['semrules'])

    global ontology_db
    ontology_db = []
    with open(semrep_config['ontology_db'], 'r') as f:
        for line in f:
            line = line.strip().split('|')
            ontology_db.append(line)

def setup_server_config(server_config):
    """Load NLP preprocessing libraries with the specified configurations

    Args:
        nlp_config (dict or configparser.SectionProxy): configuration settings
    """
    global servers
    servers = dict(server_config)

def process_directory(input_file_format, input_dir_path, output_dir_path = None):
    """Reads and processes files from a directory

    Args:
        input_file_format (str): format of the files to process (plaintext, medline, or medlinexml)
        input_dir_path (str): path to the directory to process
        output_dir_path (str): path to the output directory (optional)
    """

    for filename in os.listdir(input_dir_path):
        if filename != '.DS_Store':
            process_file(input_file_format, os.path.join(input_dir_path, filename), output_dir_path, False)

def process_file(input_file_format, input_file_path, output_file_path = None, multiple_documents = True):
    """Reads and processes a single file

    Args:
        input_file_format (str): format of the files to process (plaintext, medline, or medlinexml)
        input_file_path (str): path to the file to process
        output_dir_path (str): path to the output file (optional)
    """
    if input_file_format == 'plaintext':
        docs = read_plaintext_file(input_file_path)
    elif input_file_format == 'medline':
        docs = parse_medline_file(input_file_path)
    elif input_file_format == 'medlinexml':
        docs = parse_medlinexml_file(input_file_path)

    for doc in docs:
        # print('PMID: {}'.format(doc.PMID))
        # print('Title: {}'.format(doc.title))
        print2log(f'PMID: {doc.PMID},Title: {doc.title}')
        if doc.title is not None:
            process_text(doc.title)
        process_text(doc.abstract)

def process_interactive(output_path = None):
    """Repeatedly processes a single line of input until user enters quit

    Args:
        output_path (str): path to the output file (optional)
    """
    print2log('Please enter text. Each input will be processed as a single document. Type quit to exit interactive session.')
    while True:
        text_input = input()
        if text_input != 'quit':
            process_text(text_input)
        else:
            exit()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract semantic predictions from sentences.')
    parser.add_argument('--config_file', type=str, help='File containing configurations (see default.config for default configuration)')
    parser.add_argument('--input_format', type=str, choices=['dir', 'file', 'interactive'],
                        help='Input format. Can be a single file, directory of files, or interactive input')
    parser.add_argument('--input_file_format', type=str, choices=['plaintext', 'medline', 'medlinexml'],
                        help='Format of the input file(s). input_format must be dir or file. Interactive defaults to plaintext.')
    parser.add_argument('--input_path', type=str, help='Path to input directory or file')
    parser.add_argument('--output_path', type=str, help='Path to output directory or file')

    args = parser.parse_args()

    # use config file provided by user, else use default config file
    if args.config_file is None:
        args.config_file = 'default.config'
        print2log('No configuration file specified. Using default configuration.')
    elif not os.path.exists(args.config_file):
        print2log('Unable to locate configuration file. Please check the specified file path.')
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), args.config_file)

    # read config file
    # raises an error if there are issues reading the config file
    global config # global so we can access it from other functions
    config = configparser.ConfigParser()
    config.read(args.config_file)
    for arg, value in vars(args).items():
        if value is None and arg in config['I/O']:
            setattr(args, arg, config['I/O'][arg])

    # if input is a directory or file, the path must be specified
    if args.input_format in ['dir', 'file'] and (args.input_path is None or args.output_path is None):
        parser.error("Directory or file input format requires --input_path and --output_path.")

    if args.input_path is not None and not os.path.exists(args.input_path):
        parser.error("Input path does not exist. Please enter a valid input path.")

    if not os.path.exists(args.output_path):
        print2log('Output path does not exist. Creating directory..')
        os.makedirs(args.output_path)

    setup_server_config(config['SERVERS'])
    setup_nlp_config(config['NLP'])
    setup_semrep_config(config['SEMREP'])


    if args.input_format == 'dir':
        process_directory(args.input_file_format, args.input_path, args.output_path)
    elif args.input_format == 'file':
        process_file(args.input_file_format, args.input_path, args.output_path)
    else:
        process_interactive(args.output_path)
