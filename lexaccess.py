from jsonrpclib.jsonrpc import ServerProxy
import xml.etree.ElementTree as ET

POS_MAPPINGS = {
    'CC' : ['conj'],
    'CD' : ['num'],
    'NN' : ['noun'],
    'DT' : ['det'],
    'EX' : ['adv'],
    'FW' : [],
    'IN' : ['prep', 'conj', 'compl'],
    'JJ' : ['adj', 'verb'],
    'JJR' : ['adj', 'verb'],
    'JJS' : ['adj', 'verb'],
    'LS' : [],
    'MD' : ['modal'],
    'NN' : ['noun'],
    'NNS' : ['noun'],
    'NNP' : ['noun'],
    'NNPS' : ['noun'],
    'PDT' : ['det'],
    'POS' : ['noun'],
    'PRP' : ['pron'],
    'PRP$' : ['pron'],
    'RB' : ['adv'],
    'RBR' : ['adv'],
    'RBS' : ['adv'],
    'RP' : [],
    'SYM' : ['noun'],
    'TO' : ['adv'],
    'UH' : [],
    'VB' : ['aux', 'verb'],
    'VBD' : ['aux', 'verb'],
    'VBG' : ['aux', 'verb'],
    'VBN' : ['aux', 'verb'],
    'VBP' : ['aux', 'verb'],
    'VBZ' : ['aux', 'verb'],
    'WDT' : ['pron'],
    'WP' : ['pron'],
    'WP$' : ['pron'],
    'WRB': ['adv']
}

DISALLOWED_MATCHES = {
    'lower' : 'lour'
}

class LexRecord:
    """
    Sample XMl record:
    <lexRecord>
        <base>sex hormone</base>
        <eui>E0055508</eui>
        <cat>noun</cat>
        <spellingVars>sex-hormone</spellingVars>
        <inflVars cat="noun" cit="sex hormone" eui="E0055508" infl="base" type="basic" unInfl="sex hormone">sex hormone</inflVars>
        <inflVars cat="noun" cit="sex hormone" eui="E0055508" infl="singular" type="basic" unInfl="sex hormone">sex hormone</inflVars>
        <inflVars cat="noun" cit="sex hormone" eui="E0055508" infl="plural" type="reg" unInfl="sex hormone">sex hormones</inflVars>
        <inflVars cat="noun" cit="sex hormone" eui="E0055508" infl="base" type="basic" unInfl="sex-hormone">sex-hormone</inflVars>
        <inflVars cat="noun" cit="sex hormone" eui="E0055508" infl="singular" type="basic" unInfl="sex-hormone">sex-hormone</inflVars>
        <inflVars cat="noun" cit="sex hormone" eui="E0055508" infl="plural" type="reg" unInfl="sex-hormone">sex-hormones</inflVars>
        <nounEntry>
          <variants>reg</variants>
        </nounEntry>
    </lexRecord>
    """
    def __init__(self, record_xml):
        self.base = record_xml.find('base').text
        self.eui = record_xml.find('eui').text
        self.cat = record_xml.find('cat').text
        #self.spelling_vars = record_xml.find('spellingVars').text

        # let's keep these two as XML for now
        #self.infl_vars = record_xml.find('inflVars')
        #self.noun_entry = record_xml.find('nounEntry')

class LexAccess():
    def __init__(self, config):
        host = config['host']
        port = int(config['port'])
        self.server = ServerProxy("http://%s:%d" % (host, port))

    def lookup(self, text):
        try:
            match = self.server.parse(text)
            tree = ET.ElementTree(ET.fromstring(match.strip()))
            root = tree.getroot()

            lexrecords_xml = root.findall('lexRecord')
            if len(lexrecords_xml) > 0:
                return lexrecords_xml
        except Exception as e:
            print(e)
            print('LexAccess error: ' + e)
        return None

    # convert lex records xml to list of lex records object
    # perform text and pos filtering in this step too
    def parse_lexrecords(self, lexrecords_xml, text, allowed_pos = None):
        lexrecords = []
        for record_xml in lexrecords_xml:
            lexrecord = LexRecord(record_xml)
            if text in DISALLOWED_MATCHES and lexrecord.base == DISALLOWED_MATCHES[text]:
                continue
            if allowed_pos is not None and lexrecord.cat not in POS_MAPPINGS[allowed_pos]:
                continue

            lexrecords.append(lexrecord)
        return lexrecords

    def get_matches(self, spacy_sentence):
        matches = []

        prev_token_index = 0
        prev_lex_record = None

        # find a match for each token, either by itself or as part of a phrase
        for token in spacy_sentence:
            lookup_text = spacy_sentence[prev_token_index:token.i + 1].text

            lexrecords_xml = self.lookup(lookup_text)

            # if we find a record, try and match a longer string
            if lexrecords_xml is not None:
                prev_lexrecords = lexrecords_xml
                continue

            # if not, save the current record (if any)
            if prev_lexrecords is not None:
                text = spacy_sentence[prev_token_index:token.i]
                if len(text) == 1:
                    allowed_pos = spacy_sentence[prev_token_index].tag_
                else:
                    allowed_pos = None

                lexrecords = self.parse_lexrecords(prev_lexrecords, text, allowed_pos)

                matches.append((text, lexrecords))
                prev_lexrecords = None

            elif lookup_text != token.text:
                prev_lexrecords = self.lookup(token.text)

            prev_token_index = token.i

        return matches