#!/usr/bin/env python3
# coding: utf-8
# File: sentence_parser.py
# Author: lhy<lhy_in_blcu@126.com,https://huangyong.github.io>
# Date: 18-3-10

import os, re
from ddparser import DDParser

class SVOParser:
    def __init__(self):
        self.parser = DDParser(use_pos=True)
        print('loaded model')

    '''文章分句处理, 切分长句，冒号，分号，感叹号等做切分标识'''

    def split_sents(self, content):
        return [sentence for sentence in re.split(r'[？?！!。；;：:\n\r]', content) if sentence]

    '''句法分析---为句子中的每个词语维护一个保存句法依存儿子节点的字典'''
    def build_parse_child_dict(self, words, postags, rel_id, relation):
        child_dict_list = []
        format_parse_list = []
        for index in range(len(words)):
            child_dict = dict()
            for arc_index in range(len(rel_id)):
                if rel_id[arc_index] == index+1:   #arcs的索引从1开始
                    if rel_id[arc_index] in child_dict:
                        child_dict[relation[arc_index]].append(arc_index)
                    else:
                        child_dict[relation[arc_index]] = []
                        child_dict[relation[arc_index]].append(arc_index)
            child_dict_list.append(child_dict)
        heads = ['Root' if id == 0 else words[id - 1] for id in rel_id]  # 匹配依存父节点词语
        for i in range(len(words)):
            # ['ATT', '李克强', 0, 'nh', '总理', 1, 'n']
            a = [relation[i], words[i], i, postags[i], heads[i], rel_id[i]-1, postags[rel_id[i]-1]]
            format_parse_list.append(a)

        return child_dict_list, format_parse_list

    '''parser主函数'''
    def parser_main(self, sentence):
        res = self.parser.parse(sentence, )[0]
        words = res["word"]
        postags = res["postag"]
        rel_id = res["head"]
        relation = res["deprel"]

        child_dict_list, format_parse_list = self.build_parse_child_dict(words, postags, rel_id, relation)
        return words, postags, child_dict_list, format_parse_list

    """将所有的ATT进行合并"""
    def merge_ATT(self, words, postags, format_parse_list):
        words_ = words
        retain_nodes = set()
        ATTs = []
        ATT = []
        format_parse_list_ = []
        for parse in format_parse_list:
            dep = parse[0]
            if dep in ['ATT', 'ADV']:
                ATT += [parse[2], parse[5]]
            else:
                if ATT:
                    body = ''.join([words[i] for i in sorted(set(ATT))])
                    ATTs.append(body)
                    retain_nodes.add(sorted(set(ATT))[-1])
                    words_[sorted(set(ATT))[-1]] = body
                else:
                    retain_nodes.add(parse[2])
                ATT = []
        for indx, parse in enumerate(format_parse_list):
            if indx in retain_nodes:
                parse_ = [parse[0], words_[indx], indx, postags[indx], words_[parse[5]], parse[5], postags[parse[5]]]
                format_parse_list_.append(parse_)
        return words_, postags, format_parse_list_, retain_nodes

    """基于该结果，提取三元组"""
    def extract(self, words, postags, child_dict_list, arcs, retain_nodes):
        svos = []
        for index in range(len(postags)):
            if index not in retain_nodes:
                continue
            tmp = 1
            # 如果语义角色标记为空，则使用依存句法进行抽取
            if postags[index]:
                # 抽取以谓词为中心的事实三元组
                child_dict = child_dict_list[index]
                # 主谓宾
                if 'SBV' in child_dict and 'VOB' in child_dict:
                    # e1s = self.expand_e(words, postags, child_dict_list, child_dict['SBV'][0])
                    # e2s = self.expand_e(words, postags, child_dict_list, child_dict['VOB'][0])
                    r = words[index]
                    e1 = words[child_dict['SBV'][0]]
                    e2 = words[child_dict['VOB'][0]]
                    if e1.replace(' ', '') and e2.replace(' ', ''):
                        svos.append([e1, r, e2])

                # 含有介宾关系的主谓动补关系
                if 'SBV' in child_dict and 'CMP' in child_dict:
                    e1 = words[child_dict['SBV'][0]]
                    cmp_index = child_dict['CMP'][0]
                    r = words[index] + words[cmp_index]
                    if 'POB' in child_dict_list[cmp_index]:
                        e2 = words[child_dict_list[cmp_index]['POB'][0]]
                        if e1.replace(' ', '') and e2.replace(' ', ''):
                            svos.append([e1, r, e2])

        return svos

    '''三元组抽取主函数'''

    def ruler2(self, words, postags, child_dict_list, arcs):
        svos = []
        for index in range(len(postags)):
            tmp = 1
            # 先借助语义角色标注的结果，进行三元组抽取
            if tmp == 1:
                # 如果语义角色标记为空，则使用依存句法进行抽取
                # if postags[index] == 'v':
                if postags[index]:
                    # 抽取以谓词为中心的事实三元组
                    child_dict = child_dict_list[index]
                    # 主谓宾
                    if 'SBV' in child_dict and 'VOB' in child_dict:
                        r = words[index]
                        e1 = self.complete_e(words, postags, child_dict_list, child_dict['SBV'][0])
                        e2 = self.complete_e(words, postags, child_dict_list, child_dict['VOB'][0])
                        if e1.replace(' ', '') and e2.replace(' ', ''):
                            svos.append([e1, r, e2])

                    # 定语后置，动宾关系
                    relation = arcs[index][0]
                    head = arcs[index][2]
                    if relation == 'ATT':
                        if 'VOB' in child_dict:
                            e1 = self.complete_e(words, postags, child_dict_list, head - 1)
                            r = words[index]
                            e2 = self.complete_e(words, postags, child_dict_list, child_dict['VOB'][0])
                            temp_string = r + e2
                            if temp_string == e1[:len(temp_string)]:
                                e1 = e1[len(temp_string):]
                            if temp_string not in e1:
                                if e1.replace(' ', '') and e2.replace(' ', ''):
                                    svos.append([e1, r, e2])

                    # 含有介宾关系的主谓动补关系
                    if 'SBV' in child_dict and 'CMP' in child_dict:
                        e1 = self.complete_e(words, postags, child_dict_list, child_dict['SBV'][0])
                        cmp_index = child_dict['CMP'][0]
                        r = words[index] + words[cmp_index]
                        if 'POB' in child_dict_list[cmp_index]:
                            e2 = self.complete_e(words, postags, child_dict_list, child_dict_list[cmp_index]['POB'][0])
                            if e1.replace(' ', '') and e2.replace(' ', ''):
                                svos.append([e1, r, e2])
        return svos

    '''对找出的主语或者宾语进行扩展'''

    def complete_e(self, words, postags, child_dict_list, word_index):
        child_dict = child_dict_list[word_index]
        prefix = ''
        if 'ATT' in child_dict:
            for i in range(len(child_dict['ATT'])):
                prefix += self.complete_e(words, postags, child_dict_list, child_dict['ATT'][i])
        postfix = ''
        if postags[word_index] == 'v':
            if 'VOB' in child_dict:
                postfix += self.complete_e(words, postags, child_dict_list, child_dict['VOB'][0])
            if 'SBV' in child_dict:
                prefix = self.complete_e(words, postags, child_dict_list, child_dict['SBV'][0]) + prefix

        return prefix + words[word_index] + postfix

    '''程序主控函数'''

    def triples_main(self, content):
        sentences = self.split_sents(content)
        svos = []
        for sentence in sentences:
            print(sentence)
            words, postags, child_dict_list, arcs = self.parser_main(sentence)
            svo = self.ruler2(words, postags, child_dict_list, arcs)
            svos += svo

        return svos

'''测试'''
def test():
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
    content4 = '李克强总理今天来我家了,我感到非常荣幸'
    content5 = ''' 以色列国防军20日对加沙地带实施轰炸，造成3名巴勒斯坦武装人员死亡。此外，巴勒斯坦人与以色列士兵当天在加沙地带与以交界地区发生冲突，一名巴勒斯坦人被打死。当天的冲突还造成210名巴勒斯坦人受伤。
    当天，数千名巴勒斯坦人在加沙地带边境地区继续“回归大游行”抗议活动。部分示威者燃烧轮胎，并向以军投掷石块、燃烧瓶等，驻守边境的以军士兵向示威人群发射催泪瓦斯并开枪射击。'''
    extractor = SVOParser()
    svos = extractor.triples_main(content2)
    print('svos', svos)
    for svo in svos:
        print(svo)



if __name__ == '__main__':
    print("loading model...")
    test()

