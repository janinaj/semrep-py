import re


class SemrepSentenceSplitter:
    def __init__(self):
        self.NON_PRINTABLE_PATTERN = re.compile(r"^(\s+)$")
        self.TEXT_PATTERN = re.compile(r"[\w]")
        self.NON_UPPER_PATTERN = re.compile(r"^[^A-Z]")
        self.END_COMMA_PATTERN = re.compile(r", *(?!(\r?\n)+)$")
        self.END_PATTERN = re.compile(r"(?=(\r?\n)+)$")
        self.BACTERIA_PATTERN = re.compile(
            r"\b[A-Z]+(\.(\r?\n)+|\. +|\?(\r?\n)+|!(\r?\n)+|\? +|! +|(\r?\n)+)$")
        self.OTHER_PATTERN = re.compile(
            r"\b([A-Z]|Figs*|et al|et al|i\.e|e\.g|vs|ca|min|sec|no|Dr|Inc|INC|Co|CO|Ltd|LTD|St|b\.i\.d)(\. +)$")
        self.MIDDEN_OF_SENTENCE_PATTERN = re.compile(
            r"\b([A-Z]|Figs*|et al|et al|i\.e|e\.g|vs|Dr|Drs|Prof|no|Ms|St|b\.i\.d)(\. +)$")

    def merge(sentences):
        ori_n = len(sentences[0]['sentence'])
        sentences[0]['sentence'] = sentences[0]['sentence'].lstrip()
        new_n = len(sentences[0]['sentence'])
        sentences[0]['span'][0] += new_n - ori_n
        segmentedsentence = [sentences[0]]
        previous = sentences[0]['sentence'].lstrip()
        for i in range(1, len(sentences)):
            current = sentences[i]['sentence'].lstrip()
            if re.search(self.NON_PRINTABLE_PATTERN, current) or current.__len__() == 0:
                continue
            if re.search(self.MIDDEN_OF_SENTENCE_PATTERN, previous):
                segmentedsentence[-1]['sentence'] = segmentedsentence[-1]['sentence'] + current
                segmentedsentence[-1]['span'][1] = sentences[i]['span'][1]
            elif re.search(self.NON_UPPER_PATTERN, current) and (
                    re.search(BACTERIA_PATTERN, previous) or re.search(OTHER_PATTERN, previous)):
                segmentedsentence[-1]['sentence'] = segmentedsentence[-1]['sentence'] + current
                segmentedsentence[-1]['span'][1] = sentences[i]['span'][1]
            elif not re.search(self.TEXT_PATTERN, current) and not re.search(END_PATTERN, previous):
                segmentedsentence[-1]['sentence'] = segmentedsentence[-1]['sentence'] + current
                segmentedsentence[-1]['span'][1] = sentences[i]['span'][1]
            elif re.search(self.END_COMMA_PATTERN, previous):
                segmentedsentence[-1]['sentence'] = segmentedsentence[-1]['sentence'] + current
                segmentedsentence[-1]['span'][1] = sentences[i]['span'][1]
            else:
                segmentedsentence.append({'sentence': current, 'span': sentences[i]['span']})
            previous = current
        return segmentedsentence

    def getOverlap(a, b):
        return max(0, min(a[1], b[1]) - max(a[0], b[0]))

    def sort_check(section_header):
        section = []
        for i in section_header:
            n = int(len(section_header[i]) / 2)
            for j in range(n):
                section.append([i, section_header[i][2 * j], section_header[i][2 * j + 1]])
        section = sorted(section, key=lambda x: -x[1])
        remove_list = []
        for i in range(len(section)):
            if section[i][0] == '':
                for j in range(len(section)):
                    if j != i:
                        com = getOverlap(section[i][1:], section[j][1:])
                        if com > 0:
                            remove_list.append(i)
        for i in sorted(set(remove_list), key=lambda x: -x):
            del section[i]
        return section

    def split(full_text, section_header=None):
        pattern = re.compile(r"(.+?)(\. *(\r?\n)+|\? *(\r?\n)+|! *(\r?\n)+|\. +|\? +|! +|(\r?\n)+|\.[\"”]|[^0-9]\.[\"”]?[1-9][\[\]0-9,\-– ]*(?![.0-9]+)|[0-9]\.’?[1-9][\[\]0-9,\-– ]*(?=[A-Z][a-z])|$)")
        all_result = re.findall(pattern, full_text)
        sentences = []
        start = 0
        for res_tuple in all_result:
            text = ''.join(res_tuple[:2])
            while full_text[start] != text[0]:
                start += 1

            sentences.append({'sentence': text,
                              'span': [start, start + text.__len__() - 1]})
            start += text.__len__()

        sentences = merge(sentences)
        for i in sentences:
            ori = len(i['sentence'])
            i['sentence'] = i['sentence'].strip()
            after = len(i['sentence'])
            offset = ori - after
            if ori - after > 0:
                i['span'][1] -= offset

            if section_header:
                i['section'] = []
                for sec in section_header:
                    span = sec[1:]
                    if i['span'][0] >= span[0] - 1 and i['span'][1] <= span[1] + 1:
                        i['section'].append(sec[0])
        return sentences

# if __name__ == '__main__':
#     #sentences = segment('Although Boxer et al. 28, 29 did not demonstrate improvements in cardiac function or objective measures of muscle strength and exercise capacity in 64 chronic HF patients (of whom 34 underwent echocardiography) randomized to weekly doses of 50,000 IU of vitamin D3 for 6 months, there was an improvement in serum aldosterone and quality of life in those allocated the supplement.')
#     # sentences = segment('After a 2-week screening period, eligible patients were randomly assigned in a 1:1:1:1 ratio to one of four treatment groups: tenapanor 5 mg, 20 mg, or 50 mg twice daily (b.i.d.; dosed as the hydrochloride salt) or placebo b.i.d. Patients received tenapanor or placebo for 12 consecutive weeks, after which they were followed up for an additional 4 weeks.')
#     sentences =segment('Samples were centrifuged at 1900 g, and the supernatant was collected and stored at 4°C. J774 cells were radiolabeled for 24\u2005hours in a medium containing 2 μCi of [3H]-cholesterol per microlitre.')
#
#     print(sentences)
#     print(o)
#     # sentences = segment('The assessors disagreed in 51 cases: in three cases the disagreement was between whether the plantar wart was “cleared” or “not cleared,” in five cases it was between “cleared” and “unable to assess,” and in the remaining 43 cases it was between “not cleared” and “unable to assess.” This might lead to an underestimation of the clearance rate, but as the assessment was blind to treatment allocation it is unlikely to lead to a difference between the two treatments groups.')
#     # sentences = segment('Analysis of induced sputum provides information about cell counts (eosinophils, neutrophils, lymphocytes, macrophages) and cell activity by mediator concentrations (e.g. ECP, MPO and IL-8).')
#     print(sentences)
#     p = re.compile(r"\b")
#     print(re.search(p, 'We \b assessed circulating EPC levels and EPC outgrowth number and function in CRS patients compared to healthy controls, and evaluated whether short-term (18 days) and long-term (52 weeks) EPO therapy improved EPC number and function in patients with CRS.\n      Methods'))
# patients compared to healthy controls, and evaluated whether short-term (18 days) and long-term (52 weeks) EPO therapy improved EPC number and function in patients with CRS.\n      Methods'))
