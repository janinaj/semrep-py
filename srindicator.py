import xml.etree.ElementTree as ET
from spacy.tokens import Token

class SRIndicator:
    """
        Sample XMl record:
        <SRIndicator string="abate" gapType="none" type="l" verified="true">
            <Lexeme lemma="abate" pos="VB"/>
            <SemInfo category="affects" cue="" inverse="false" negated="false"/>
            <SemInfo category="disrupts" cue="" inverse="false" negated="false"/>
        </SRIndicator>
    """

    def __init__(self, srindicator_xml):
        self.string = srindicator_xml.attrib['string']
        self.gap_type = srindicator_xml.attrib['gapType']
        self.type = srindicator_xml.attrib['type']

        if srindicator_xml.attrib['verified'] == 'true':
            self.verified = True
        elif srindicator_xml.attrib['verified'] == 'false':
            self.verified = False
        else:
            # throw error here instead of exiting
            print(f'Indicator Error: {self.string}. verified can only be true or false.')
            print('Check indicator file.')
            exit()

        lexeme_xml = srindicator_xml.findall('Lexeme')
        self.lexeme = []
        if len(lexeme_xml) == 1:
            self.lexeme = [{'lemma': lexeme_xml[0].attrib['lemma'],
                     'pos': lexeme_xml[0].attrib['pos']}]
            self.lexeme_type = 'single'
        elif len(lexeme_xml) > 1:
            for lexeme_xml in lexeme_xml:
                self.lexeme.append({'lemma': lexeme_xml.attrib['lemma'],
                               'pos': lexeme_xml.attrib['pos']})
            self.lexeme_type = 'multiword'
        else:
            gapped_lexeme = srindicator_xml.find('GappedLexeme')

            if gapped_lexeme is not None:
                for lexeme in gapped_lexeme.findall('Part/Lexeme'):
                    self.lexeme.append({'lemma': lexeme.attrib['lemma'],
                     'pos': lexeme.attrib['pos']})

                self.lexeme_type = 'gapped'
            else:
                input(self.string)

        self.senses = []
        for seminfo_xml in srindicator_xml.findall('SemInfo'):
            self.senses.append(Sense(seminfo_xml))

    def get_most_probable_sense(self):
        return self.senses[0]

class Sense:
    """
        Sample XMl record:
        <SemInfo category="affects" cue="" inverse="false" negated="false"/>
    """

    def __init__(self, seminfo_xml):

        self.category = seminfo_xml.attrib['category']

        # if 'cue' in seminfo_xml.attrib:
        self.cue = seminfo_xml.attrib['cue']
        # else:
        #     self.cue = None

        if seminfo_xml.attrib['inverse'] == 'true':
            self.inverse = True
        elif seminfo_xml.attrib['inverse'] == 'false':
            self.inverse = False
        else:
            # throw error here instead of exiting
            print(f'Indicator Error: {self.string}. inverse can only be true or false.')
            print('Check indicator file.')
            exit()

        if seminfo_xml.attrib['negated'] == 'true':
            self.negated = True
        elif seminfo_xml.attrib['negated'] == 'false':
            self.negated = False
        else:
            # throw error here instead of exiting
            print(f'Indicator Error: {self.string}. inverse can only be true or false.')
            print('Check indicator file.')
            exit()

def parse_semrules_file(filename):
    tree = ET.parse(filename)
    root = tree.getroot()

    srindicators_list = []
    srindicator_lemmas = {}
    for i, srindicator_xml in enumerate(root.findall('SRIndicator')):
        srindicator = SRIndicator(srindicator_xml)
        srindicators_list.append(srindicator)

        if srindicator.lexeme_type not in srindicator_lemmas:
            srindicator_lemmas[srindicator.lexeme_type] = {}
        if srindicator.lexeme[0]['lemma'] not in srindicator_lemmas[srindicator.lexeme_type]:
            srindicator_lemmas[srindicator.lexeme_type][srindicator.lexeme[0]['lemma']] = []
        srindicator_lemmas[srindicator.lexeme_type][srindicator.lexeme[0]['lemma']].append(i)

    # sort indicators list
    # single_word_indicators = {}
    indicators_by_lexeme_length = {}
    for indicator in srindicators_list:
        num_lexeme = len(indicator.lexeme)
        # if num_lexeme == 0:
        #     print('No lexeme')
        #     print(indicator.string)
        # elif num_lexeme == 1:
        #     if indicator.string not in single_word_indicators:
        #         single_word_indicators[indicator.string] = []
        #     single_word_indicators[indicator.string].append(indicator)
        if num_lexeme not in indicators_by_lexeme_length:
            indicators_by_lexeme_length[num_lexeme] = {}
        if indicator.string not in indicators_by_lexeme_length[num_lexeme]:
            indicators_by_lexeme_length[num_lexeme][indicator.string] = []
        indicators_by_lexeme_length[num_lexeme][indicator.string].append(indicator)

    lengths = list(indicators_by_lexeme_length.keys())
    lengths.sort(reverse = True)

    srindicators = []
    for length in lengths:
        indicator_strings = list(indicators_by_lexeme_length[length].keys())
        indicator_strings.sort()

        for indicator_string in indicator_strings:
            for indicator in indicators_by_lexeme_length[length][indicator_string]:
                srindicators.append(indicator)

    return srindicators, srindicator_lemmas

# def annotate_indicators(spacy_sentence, srindicators_list, srindicator_lemmas):
#     indicator_getter = lambda token: token.text in ("apple", "pear", "banana")
#
#     lexeme_type_order = ['gapped', 'multiword', 'single']
#
#     indicators = []
#     for lexeme_type in lexeme_type_order:
#         for token in spacy_sentence:
#             if token.lemma_ in srindicator_lemmas[lexeme_type]:
#                 if lexeme_type == 'gapped':
#                    for next_token in spacy_sentence[token.i + 1:]:
#                        if next_token.lemma_ == srindicator_lemmas[lexeme_type][token.lemma_]:
#                            pass
#                 elif lexeme_type == 'multiword':
#                     for next_token in spacy_sentence[token.i + 1:]:
#                         if next_token.lemma_ == srindicator_lemmas[lexeme_type][token.lemma_]:
#                             pass
#                 else:
#                     Token.set_extension('is_indicator', default = True, force = True)
#                     indicators.append(token.i)
#
#     return indicators