# coding=utf-8
import re, os
import jieba.posseg as pseg

class ExtractEvent:
    def __init__(self):
        self.map_dict = self.load_mapdict()
        self.minlen = 2
        self.maxlen = 30
        self.keywords_num = 20
        self.limit_score = 10
        self.IP = "(([NERMQ]*P*[ABDP]*)*([ABDV]{1,})*([NERMQ]*)*([VDAB]$)?([NERMQ]*)*([VDAB]$)?)*"
        self.IP = "([NER]*([PMBQADP]*[NER]*)*([VPDA]{1,}[NEBRVMQDA]*)*)"
        self.MQ = '[DP]*M{1,}[Q]*([VN]$)?'
        self.VNP = 'V*N{1,}'
        self.NP = '[NER]{1,}'
        self.REN = 'R{2,}'
        self.VP = 'P?(V|A$|D$){1,}'
        self.PP = 'P?[NERMQ]{1,}'
        self.SPO_n = "n{1,}"
        self.SPO_v = "v{1,}"
        self.stop_tags = {'u', 'wp', 'o', 'y', 'w', 'f', 'u', 'c', 'uj', 'nd', 't', 'x'}
        self.combine_words = {"首先", "然后", "之前", "之后", "其次", "接着"}

    """构建映射字典"""
    def load_mapdict(self):
        tag_dict = {
            'B': 'b'.split(),  # 时间词
            'A': 'a d'.split(),  # 时间词
            'D': "d".split(),  # 限定词
            'N': "n j s zg en l r".split(),  #名词
            "E": "nt nz ns an ng".split(),  #实体词
            "R": "nr".split(),  #人物
            'G': "g".split(),  #语素
            'V': "vd v va i vg vn g".split(), #动词
            'P': "p f".split(),  #介词
            "M": "m t".split(),  #数词
            "Q": "q".split(), #量词
            "v": "V".split(), #动词短语
            "n": "N".split(), #名词介宾短语
        }
        map_dict = {}
        for flag, tags in tag_dict.items():
            for tag in tags:
                map_dict[tag] = flag
        return map_dict

    """根据定义的标签,对词性进行标签化"""
    def transfer_tags(self, postags):
        tags = [self.map_dict.get(tag[:2], 'W') for tag in postags]
        return ''.join(tags)

    """抽取出指定长度的ngram"""
    def extract_ngram(self, pos_seq, regex):
        ss = self.transfer_tags(pos_seq)
        def gen():
            for s in range(len(ss)):
                for n in range(self.minlen, 1 + min(self.maxlen, len(ss) - s)):
                    e = s + n
                    substr = ss[s:e]
                    if re.match(regex + "$", substr):
                        yield (s, e)
        return list(gen())

    '''抽取ngram'''
    def extract_sentgram(self, pos_seq, regex):
        ss = self.transfer_tags(pos_seq)
        def gen():
            for m in re.finditer(regex, ss):
                yield (m.start(), m.end())
        return list(gen())

    """指示代词替换，消解处理"""
    def cite_resolution(self, words, postags, persons):
        if not persons and 'r' not in set(postags):
            return words, postags
        elif persons and 'r' in set(postags):
            cite_index = postags.index('r')
            if words[cite_index] in {"其", "他", "她", "我"}:
                words[cite_index] = persons[-1]
                postags[cite_index] = 'nr'
        elif 'r' in set(postags):
            cite_index = postags.index('r')
            if words[cite_index] in {"为何", "何", "如何"}:
                postags[cite_index] = 'w'
        return words, postags

    """抽取量词性短语"""
    def extract_mqs(self, wds, postags):
        phrase_tokspans = self.extract_sentgram(postags, self.MQ)
        if not phrase_tokspans:
            return []
        phrases = [''.join(wds[i[0]:i[1]])for i in phrase_tokspans]
        return phrases

    '''抽取动词性短语'''
    def get_ips(self, wds, postags):
        ips = []
        phrase_tokspans = self.extract_sentgram(postags, self.IP)
        if not phrase_tokspans:
            return []
        phrases = [''.join(wds[i[0]:i[1]])for i in phrase_tokspans]
        phrase_postags = [''.join(postags[i[0]:i[1]]) for i in phrase_tokspans]
        for phrase, phrase_postag_ in zip(phrases, phrase_postags):
            if not phrase:
                continue
            phrase_postags = ''.join(phrase_postag_).replace('m', '').replace('q','').replace('a', '').replace('t', '')
            if phrase_postags.startswith('n') or phrase_postags.startswith('j'):
                has_subj = 1
            else:
                has_subj = 0
            ips.append((has_subj, phrase))
        return ips

    """分短句处理"""
    def split_short_sents(self, text):
        return [i for i in re.split(r'[,，]', text) if len(i)>2]
    """分段落"""
    def split_paras(self, text):
        return [i for i in re.split(r'[\n\r]', text) if len(i) > 4]

    """分长句处理"""
    def split_long_sents(self, text):
        return [i for i in re.split(r'[;。:； ：？?!！【】▲丨|]', text) if len(i) > 4]

    """移出噪声数据"""
    def remove_punc(self, text):
        text = text.replace('\u3000', '').replace("'", '').replace('“', '').replace('”', '').replace('▲','').replace('” ', "”")
        tmps = re.findall('[\(|（][^\(（\)）]*[\)|）]', text)
        for tmp in tmps:
            text = text.replace(tmp, '')
        return text

    """保持专有名词"""
    def zhuanming(self, text):
        books = re.findall('[<《][^《》]*[》>]', text)
        return books

    """对人物类词语进行修正"""
    def modify_nr(self, wds, postags):
        phrase_tokspans = self.extract_sentgram(postags, self.REN)
        wds_seq = ' '.join(wds)
        pos_seq = ' '.join(postags)
        if not phrase_tokspans:
            return wds, postags
        else:
            wd_phrases = [' '.join(wds[i[0]:i[1]]) for i in phrase_tokspans]
            postag_phrases = [' '.join(postags[i[0]:i[1]]) for i in phrase_tokspans]
            for wd_phrase in wd_phrases:
                tmp = wd_phrase.replace(' ', '')
                wds_seq = wds_seq.replace(wd_phrase, tmp)
            for postag_phrase in postag_phrases:
                pos_seq = pos_seq.replace(postag_phrase, 'nr')
        words = [i for i in wds_seq.split(' ') if i]
        postags = [i for i in pos_seq.split(' ') if i]
        return words, postags

    """对人物类词语进行修正"""
    def modify_duplicate(self, wds, postags, regex, tag):
        phrase_tokspans = self.extract_sentgram(postags, regex)
        wds_seq = ' '.join(wds)
        pos_seq = ' '.join(postags)
        if not phrase_tokspans:
            return wds, postags
        else:
            wd_phrases = [' '.join(wds[i[0]:i[1]]) for i in phrase_tokspans]
            postag_phrases = [' '.join(postags[i[0]:i[1]]) for i in phrase_tokspans]
            for wd_phrase in wd_phrases:
                tmp = wd_phrase.replace(' ', '')
                wds_seq = wds_seq.replace(wd_phrase, tmp)
            for postag_phrase in postag_phrases:
                pos_seq = pos_seq.replace(postag_phrase, tag)
        words = [i for i in wds_seq.split(' ') if i]
        postags = [i for i in pos_seq.split(' ') if i]
        return words, postags

    '''对句子进行分词处理'''
    def cut_wds(self, sent):
        wds = list(pseg.cut(sent))
        postags = [w.flag for w in wds]
        words = [w.word for w in wds]
        return self.modify_nr(words, postags)

    """移除噪声词语"""
    def clean_wds(self, words, postags):
        wds = []
        poss =[]
        for wd, postag in zip(words, postags):
            if postag[0].lower() in self.stop_tags:
                continue
            wds.append(wd)
            poss.append(postag[:2])
        return wds, poss

    """检测是否成立, 肯定需要包括名词"""
    def check_flag(self, postags):
        if not {"v", 'a', 'i'}.intersection(postags):
            return 0
        return 1

    """识别出人名实体"""
    def detect_person(self, words, postags):
        persons = []
        for wd, postag in zip(words, postags):
            if postag == 'nr':
                persons.append(wd)
        return persons

    """识别出名词性短语"""
    def get_nps(self, wds, postags):
        phrase_tokspans = self.extract_sentgram(postags, self.NP)
        if not phrase_tokspans:
            return [],[]
        phrases_np = [''.join(wds[i[0]:i[1]]) for i in phrase_tokspans]
        return phrase_tokspans, phrases_np

    """识别出介宾短语"""
    def get_pps(self, wds, postags):
        phrase_tokspans = self.extract_sentgram(postags, self.PP)
        if not phrase_tokspans:
            return [],[]
        phrases_pp = [''.join(wds[i[0]:i[1]]) for i in phrase_tokspans]
        return phrase_tokspans, phrases_pp

    """识别出动词短语"""
    def get_vps(self, wds, postags):
        phrase_tokspans = self.extract_sentgram(postags, self.VP)
        if not phrase_tokspans:
            return [],[]
        phrases_vp = [''.join(wds[i[0]:i[1]]) for i in phrase_tokspans]
        return phrase_tokspans, phrases_vp

    """抽取名动词性短语"""
    def get_vnps(self, s):
        wds, postags = self.cut_wds(s)
        if not postags:
            return [], []
        if not (postags[-1].endswith("n") or postags[-1].endswith("l") or postags[-1].endswith("i")):
            return [], []
        phrase_tokspans = self.extract_sentgram(postags, self.VNP)
        if not phrase_tokspans:
            return [], []
        phrases_vnp = [''.join(wds[i[0]:i[1]]) for i in phrase_tokspans]
        phrase_tokspans2 = self.extract_sentgram(postags, self.NP)
        if not phrase_tokspans2:
            return [], []
        phrases_np = [''.join(wds[i[0]:i[1]]) for i in phrase_tokspans2]
        return phrases_vnp, phrases_np

    """提取短语"""
    def phrase_ip(self, content):
        spos = []
        events = []
        content = self.remove_punc(content)
        paras = self.split_paras(content)
        for para in paras:
            long_sents = self.split_long_sents(para)
            for long_sent in long_sents:
                persons = []
                short_sents = self.split_short_sents(long_sent)
                for sent in short_sents:
                    words, postags = self.cut_wds(sent)
                    person = self.detect_person(words, postags)
                    words, postags = self.cite_resolution(words, postags, persons)
                    words, postags = self.clean_wds(words, postags)
                    #print(words,postags)
                    ips = self.get_ips(words, postags)
                    persons += person
                    for ip in ips:
                        events.append(ip[1])
                        wds_tmp = []
                        postags_tmp = []
                        words, postags = self.cut_wds(ip[1])
                        verb_tokspans, verbs = self.get_vps(words, postags)
                        pp_tokspans, pps = self.get_pps(words, postags)
                        tmp_dict = {str(verb[0]) + str(verb[1]): ['V', verbs[idx]] for idx, verb in enumerate(verb_tokspans)}
                        pp_dict = {str(pp[0]) + str(pp[1]): ['N', pps[idx]] for idx, pp in enumerate(pp_tokspans)}
                        tmp_dict.update(pp_dict)
                        sort_keys = sorted([int(i) for i in tmp_dict.keys()])
                        for i in sort_keys:
                            if i < 10:
                                i = '0' + str(i)
                            wds_tmp.append(tmp_dict[str(i)][-1])
                            postags_tmp.append(tmp_dict[str(i)][0])
                        wds_tmp, postags_tmp = self.modify_duplicate(wds_tmp, postags_tmp, self.SPO_v, 'V')
                        wds_tmp, postags_tmp = self.modify_duplicate(wds_tmp, postags_tmp, self.SPO_n, 'N')
                        if len(postags_tmp) < 2:
                            continue
                        seg_index = []
                        i = 0
                        for wd, postag in zip(wds_tmp, postags_tmp):
                            if postag == 'V':
                                seg_index.append(i)
                            i += 1
                        spo = []
                        for indx, seg_indx in enumerate(seg_index):
                            if indx == 0:
                                pre_indx = 0
                            else:
                                pre_indx = seg_index[indx-1]
                            if pre_indx < 0:
                                pre_indx = 0
                            if seg_indx == 0:
                                spo.append(('', wds_tmp[seg_indx], ''.join(wds_tmp[seg_indx+1:])))
                            elif seg_indx > 0 and indx < 1:
                                spo.append((''.join(wds_tmp[:seg_indx]), wds_tmp[seg_indx], ''.join(wds_tmp[seg_indx + 1:])))
                            else:
                                spo.append((''.join(wds_tmp[pre_indx+1:seg_indx]), wds_tmp[seg_indx], ''.join(wds_tmp[seg_indx + 1:])))
                        spos += spo

        return events, spos

if __name__ == '__main__':
    import time
    handler = ExtractEvent()
    start = time.time()
    content1 = """环境很好，位置独立性很强，比较安静很切合店名，半闲居，偷得半日闲。点了比较经典的菜品，味道果然不错！烤乳鸽，超级赞赞赞，脆皮焦香，肉质细嫩，超好吃。艇仔粥料很足，香葱自己添加，很贴心。金钱肚味道不错，不过没有在广州吃的烂，牙口不好的慎点。凤爪很火候很好，推荐。最惊艳的是长寿菜，菜料十足，很新鲜，清淡又不乏味道，而且没有添加调料的味道，搭配的非常不错！"""
    content2 = """近日，一条男子高铁吃泡面被女乘客怒怼的视频引发热议。女子情绪激动，言辞激烈，大声斥责该乘客，称高铁上有规定不能吃泡面，质问其“有公德心吗”“没素质”。视频曝光后，该女子回应称，因自己的孩子对泡面过敏，曾跟这名男子沟通过，但对方执意不听，她才发泄不满，并称男子拍视频上传已侵犯了她的隐私权和名誉权，将采取法律手段。12306客服人员表示，高铁、动车上一般不卖泡面，但没有规定高铁、动车上不能吃泡面。
                高铁属于密封性较强的空间，每名乘客都有维护高铁内秩序，不破坏该空间内空气质量的义务。这也是乘客作为公民应当具备的基本品质。但是，在高铁没有明确禁止食用泡面等食物的背景下，以影响自己或孩子为由阻挠他人食用某种食品并厉声斥责，恐怕也超出了权利边界。当人们在公共场所活动时，不宜过分干涉他人权利，这样才能构建和谐美好的公共秩序。
                一般来说，个人的权利便是他人的义务，任何人不得随意侵犯他人权利，这是每个公民得以正常工作、生活的基本条件。如果权利可以被肆意侵犯而得不到救济，社会将无法运转，人们也没有幸福可言。如西谚所说，“你的权利止于我的鼻尖”，“你可以唱歌，但不能在午夜破坏我的美梦”。无论何种权利，其能够得以行使的前提是不影响他人正常生活，不违反公共利益和公序良俗。超越了这个边界，权利便不再为权利，也就不再受到保护。
                在“男子高铁吃泡面被怒怼”事件中，初一看，吃泡面男子可能侵犯公共场所秩序，被怒怼乃咎由自取，其实不尽然。虽然高铁属于封闭空间，但与禁止食用刺激性食品的地铁不同，高铁运营方虽然不建议食用泡面等刺激性食品，但并未作出禁止性规定。由此可见，即使食用泡面、榴莲、麻辣烫等食物可能产生刺激性味道，让他人不适，但是否食用该食品，依然取决于个人喜好，他人无权随意干涉乃至横加斥责。这也是此事件披露后，很多网友并未一边倒地批评食用泡面的男子，反而认为女乘客不该高声喧哗。
                现代社会，公民的义务一般分为法律义务和道德义务。如果某个行为被确定为法律义务，行为人必须遵守，一旦违反，无论是受害人抑或旁观群众，均有权制止、投诉、举报。违法者既会受到应有惩戒，也会受到道德谴责，积极制止者则属于应受鼓励的见义勇为。如果有人违反道德义务，则应受到道德和舆论谴责，并有可能被追究法律责任。如在公共场所随地吐痰、乱扔垃圾、脱掉鞋子、随意插队等。此时，如果行为人对他人的劝阻置之不理甚至行凶报复，无疑要受到严厉惩戒。
                当然，随着社会的发展，某些道德义务可能上升为法律义务。如之前，很多人对公共场所吸烟不以为然，烟民可以旁若无人地吞云吐雾。现在，要是还有人不识时务地在公共场所吸烟，必然将成为众矢之的。
                再回到“高铁吃泡面”事件，要是随着人们观念的更新，在高铁上不得吃泡面等可能产生刺激性气味的食物逐渐成为共识，或者上升到道德义务或法律义务。斥责、制止他人吃泡面将理直气壮，否则很难摆脱“矫情”，“将自我权利凌驾于他人权利之上”的嫌疑。
                在相关部门并未禁止在高铁上吃泡面的背景下，吃不吃泡面系个人权利或者个人私德，是不违反公共利益的个人正常生活的一部分。如果认为他人吃泡面让自己不适，最好是请求他人配合并加以感谢，而非站在道德制高点强制干预。只有每个人行使权利时不逾越边界，与他人沟通时好好说话，不过分自我地将幸福和舒适凌驾于他人之上，人与人之间才更趋于平等，公共生活才更趋向美好有序。"""
    content3 = '''（原标题：央视独家采访：陕西榆林产妇坠楼事件在场人员还原事情经过）
    央视新闻客户端11月24日消息，2017年8月31日晚，在陕西省榆林市第一医院绥德院区，产妇马茸茸在待产时，从医院五楼坠亡。事发后，医院方面表示，由于家属多次拒绝剖宫产，最终导致产妇难忍疼痛跳楼。但是产妇家属却声称，曾向医生多次提出剖宫产被拒绝。
    事情经过究竟如何，曾引起舆论纷纷，而随着时间的推移，更多的反思也留给了我们，只有解决了这起事件中暴露出的一些问题，比如患者的医疗选择权，人们对剖宫产和顺产的认识问题等，这样的悲剧才不会再次发生。央视记者找到了等待产妇的家属，主治医生，病区主任，以及当时的两位助产师，一位实习医生，希望通过他们的讲述，更准确地还原事情经过。
    产妇待产时坠亡，事件有何疑点。公安机关经过调查，排除他杀可能，初步认定马茸茸为跳楼自杀身亡。马茸茸为何会在医院待产期间跳楼身亡，这让所有人的目光都聚焦到了榆林第一医院，这家在当地人心目中数一数二的大医院。
    就这起事件来说，如何保障患者和家属的知情权，如何让患者和医生能够多一份实质化的沟通？这就需要与之相关的法律法规更加的细化、人性化并且充满温度。用这种温度来消除孕妇对未知的恐惧，来保障医患双方的权益，迎接新生儿平安健康地来到这个世界。'''
    content4 = '2020年9月25日，恒生电子2020年财富资管行业峰会即将在上海召开。当日下午15:00，白雪博士作《基于产业链图谱的智能投研实践》报告：近年来各行各业的数字化进程日益加速，而在投资、投研领域，投资对象数字化，投研投资过程数字化也被重视起来，越来越多的金融机构都开始依据金融知识图谱着手打造有自身特色的数据库。本次大会分为上午的外滩大会-恒生全球财富资管高峰论坛和下午的财富资管行业峰会两个半场。'
    content5 = ''' 以色列国防军20日对加沙地带实施轰炸，造成3名巴勒斯坦武装人员死亡。此外，巴勒斯坦人与以色列士兵当天在加沙地带与以交界地区发生冲突，一名巴勒斯坦人被打死。当天的冲突还造成210名巴勒斯坦人受伤。
    当天，数千名巴勒斯坦人在加沙地带边境地区继续“回归大游行”抗议活动。部分示威者燃烧轮胎，并向以军投掷石块、燃烧瓶等，驻守边境的以军士兵向示威人群发射催泪瓦斯并开枪射击。'''
    content6 = """互联网为每个人提供了展现自我的舞台，因为一句话、一个表情、一个动作而走红的不在少数，但像丁真这样引发如此大规模的网络热潮，甚至收获了外交部发言人打call的，却也罕见。有人说丁真的走红，源自于其超高的颜值和帅气的外表，也有人说丁真身上的淳朴和纯真格外打动人。事实上，这些只是让他具备了网红的潜质。真正让他成为“顶级流量”的，是他对家乡、对生活的热爱，让人们感受到逆境中成长的自强不息力量，是镜头中的雪山、白云、藏族服饰等元素，展现了一个丰富多彩而又立体的中国，唤醒了人们对诗和远方的向往，是在他走红之后依然保持的纯真本色，让人们看到一颗赤子之心。
    最近，生活在四川甘孜州理塘县的藏族小伙丁真，因为一条不到10秒的视频意外走红网络，不仅被当地聘为旅游大使，更引发了各地文旅机构助推热潮。通过丁真这个窗口让更多人了解到四川乃至全国的景点，网友纷纷表示“这才是网红最好的打开方式”。今晚，我们就从这个藏族小伙聊起。
    　11月30日警方通报了情况：涉事男生马某是山东外事职业大学大学大一在校生，18岁，女生李某是四川大学锦江学院大三在校生，21岁，两人系情侣关系，当天马某从山东乘坐飞机来到李某学校，然后通过衣物掩饰混入了李某所在宿舍楼，在宿舍内两人见面后因为感情纠纷，马某拿起了宿舍内的一把12厘米长剪刀，将李某捅致重伤后跳楼身亡。
    """
    events, spos = handler.phrase_ip(content1)
    spos = [i for i in spos if i[0] and i[2]]
    for spo in spos:
        print(spo)

    # while 1:
    #     content = input("enter an sent to parser").strip()
    #     events, spos = handler.phrase_ip(content)
    #     for spo in spos:
    #         print(spo)
    #     print('#####'*5)
    #     for event in events:
    #         print(event)