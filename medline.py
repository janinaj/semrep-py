from lxml import etree

class MedlineDocument:
    def __init__(self, doc):
        if isinstance(doc, str):
            self.PMID = None
            self.title = None
            self.abstract = doc.strip()
        elif isinstance(doc, dict):
            self.dict_to_object(doc)
        elif isinstance(doc, etree._Element):
            self.xml_to_object(doc)

    def dict_to_object(self, doc):
        # assumption: all fields are present
        self.PMID = doc['PMID'][0].strip()
        self.title = doc['TI'][0].strip()
        self.abstract = doc['AB'][0].strip()

    def xml_to_object(self, doc):
        # assumption: all fields are present
        self.PMID = doc.find('PMID').text.strip()
        self.title = doc.xpath('string(Article/ArticleTitle)').strip()

        self.abstract = ''
        for text in doc.xpath('Article/Abstract/AbstractText'):
            self.abstract += text.xpath('string(.)').strip() + ' '
        self.abstract = self.abstract.strip()

def read_plaintext_file(file_path):
    with open(file_path, 'r') as f:
        return [MedlineDocument(doc) for doc in f.readlines() if doc != '\n']

def parse_medline_file(file_path):
    medline_docs = list() # list of medline documents
    with open(file_path, 'r') as f:
        doc = {}

        lines = f.readlines()
        for i, line in enumerate(lines):
            # if line is empty or end of file is reached, add current doc to doc list
            if line == '\n' or i + 1 == len(lines):
                if doc != {}:
                    medline_docs.append(MedlineDocument(doc))
                    doc = {}
                continue

            # if 5th character is a dash, it is the start of a new field
            # else it is a continuation of the old field
            if len(line) > 5 and line[4] == '-':
                # sample line format: PMID- 15996060
                # split into field and data
                line = line.split('-', 1)
                field = line[0].strip()
                data = line[1].strip()

                if field not in doc:
                    doc[field] = [data]
                else:
                    doc[field].append(data)
            else:
                doc[field][len(doc[field]) - 1] += ' ' + line.strip()

    return medline_docs

def parse_medlinexml_file(file_path):
    medline_xml = etree.parse(file_path)
    root = medline_xml.getroot()

    medline_docs = list()
    for doc in root.findall('PubmedArticle/MedlineCitation'):
        medline_docs.append(MedlineDocument(doc))

    return medline_docs
