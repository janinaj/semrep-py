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
        self.verified = srindicator_xml.attrib['verified']

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

        self.seminfo = []
        for seminfo_xml in srindicator_xml.find('SemInfo'):
            seminfo.append(SemInfo(seminfo_xml))

class SemInfo:
    """
        Sample XMl record:
        <SemInfo category="affects" cue="" inverse="false" negated="false"/>
    """

    def __init__(self, seminfo_xml):
        self.category = srindicator_xml.attrib['category']
        self.cue = srindicator_xml.attrib['cue']
        self.inverse = srindicator_xml.attrib['inverse']
        self.negated = srindicator_xml.attrib['negated']

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
    return srindicators_list, srindicator_lemmas

def annotate_indicators(spacy_sentence, srindicators_list, srindicator_lemmas):
    indicator_getter = lambda token: token.text in ("apple", "pear", "banana")

    lexeme_type_order = ['gapped', 'multiword', 'single']

    indicators = []
    for lexeme_type in lexeme_type_order:
        for token in spacy_sentence:
            if token.lemma_ in srindicator_lemmas[lexeme_type]:
                if lexeme_type == 'gapped':
                   for next_token in spacy_sentence[token.i + 1:]:
                       if next_token.lemma_ == srindicator_lemmas[lexeme_type][token.lemma_]:
                           pass
                elif lexeme_type == 'multiword':
                    for next_token in spacy_sentence[token.i + 1:]:
                        if next_token.lemma_ == srindicator_lemmas[lexeme_type][token.lemma_]:
                            pass
                else:
                    Token.set_extension('is_indicator', default = True, force = True)
                    indicators.append(token.i)

    return indicators