# EventTriplesExtraction
EventTriplesExtraction based on dependency parser and semantic role labeling, 基于依存句法与语义角色标注的事件三元组抽取

# 使用方式
from triples_extraction import *
extractor = TripleExtractor()
svos = extractor.triples_main(content1)
        print('svos', svos)
