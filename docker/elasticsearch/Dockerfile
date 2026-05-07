FROM docker.elastic.co/elasticsearch/elasticsearch:8.13.4

# 中文 IK 分词器（value_es_repository.py 用 ik_max_word）
COPY elasticsearch-analysis-ik-8.13.4.zip /tmp/ik.zip
RUN bin/elasticsearch-plugin install --batch file:///tmp/ik.zip
