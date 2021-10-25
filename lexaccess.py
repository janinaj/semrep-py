import xml.etree.ElementTree as ET
import re
import subprocess

#don't think this is used
def print2log(s):
    import logging
    logging.info(s)
    print(s)


PREDICATIVE_CATEGORIES = set(['NN', 'VB', 'JJ', 'RB', 'PR'])

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


import functools

class LexAccess():
    def __init__(self, path):
        self.path = path

    def normalize_text(self, text):
        # print(f'lookup:{text}')
        # ctext=text.replace('(','').replace(')','').replace('>','').replace('<','')
        return re.sub(r'\W+', ' ', text)

    #@functools.lru_cache(maxsize = None)
    def get_matches(self, text):
        ctext= self.normalize_text(text).strip()
        print2log(f'lookup:{text}:[{ctext}]')

        if len(ctext) > 0:
            try:
                match = self.lookup(ctext)
                tree = ET.ElementTree(ET.fromstring(match.strip()))
                root = tree.getroot()

                lexrecords_xml = root.findall('lexRecord')
                if len(lexrecords_xml) > 0:
                    print2log(f'matched: {text}')
                    return lexrecords_xml
            except Exception as e:
                print2log(e)
                print2log(f'LexAccess error: {e}')
        return None

    def lookup(self, text):  # could make a parse method in class below
        #command = f'echo {text} | {self.path} -f:id -f:x'
        # match = os.popen(command).read()
        echo_cmd = subprocess.Popen(('echo', text), stdout = subprocess.PIPE)
        output = subprocess.check_output((self.path, '-f:id -f:x'), stdin = echo_cmd.stdout,
                                         stderr = subprocess.DEVNULL)
        echo_cmd.wait()

        return output

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


