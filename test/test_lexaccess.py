import sys
sys.path.append('..')

import xml.etree.ElementTree as ET
from lexaccess import LexAccess

def test_lookup():
    lexaccess = LexAccess({'host' : 'localhost', 'port' : 8085})

    val = lexaccess.lookup('sex hormone')
    assert(isinstance(val, list))
    assert (isinstance(val[0], ET.Element))

def test_parse_lexrecords():
    xml_string =  '''
    <?xml version="1.0" encoding="UTF-8"?>
    <lexRecords>
      <lexRecord>
        <base>sex</base>
        <eui>E0055486</eui>
        <cat>noun</cat>
        <inflVars cat="noun" cit="sex" eui="E0055486" infl="base" type="basic" unInfl="sex">sex</inflVars>
        <inflVars cat="noun" cit="sex" eui="E0055486" infl="singular" type="basic" unInfl="sex">sex</inflVars>
        <inflVars cat="noun" cit="sex" eui="E0055486" infl="plural" type="reg" unInfl="sex">sexes</inflVars>
        <nounEntry>
          <variants>reg</variants>
          <variants>uncount</variants>
        </nounEntry>
      </lexRecord>
      <lexRecord>
        <base>sex</base>
        <eui>E0055487</eui>
        <cat>verb</cat>
        <inflVars cat="verb" cit="sex" eui="E0055487" infl="base" type="basic" unInfl="sex">sex</inflVars>
        <inflVars cat="verb" cit="sex" eui="E0055487" infl="pres1p23p" type="basic" unInfl="sex">sex</inflVars>
        <inflVars cat="verb" cit="sex" eui="E0055487" infl="infinitive" type="basic" unInfl="sex">sex</inflVars>
        <inflVars cat="verb" cit="sex" eui="E0055487" infl="pres3s" type="reg" unInfl="sex">sexes</inflVars>
        <inflVars cat="verb" cit="sex" eui="E0055487" infl="past" type="reg" unInfl="sex">sexed</inflVars>
        <inflVars cat="verb" cit="sex" eui="E0055487" infl="pastPart" type="reg" unInfl="sex">sexed</inflVars>
        <inflVars cat="verb" cit="sex" eui="E0055487" infl="presPart" type="reg" unInfl="sex">sexing</inflVars>
        <verbEntry>
          <variants>reg</variants>
          <tran>np</tran>
        </verbEntry>
      </lexRecord>
    </lexRecords>
    '''
    print(xml_string)
    # parse_lexrecords
test_parse_lexrecords()