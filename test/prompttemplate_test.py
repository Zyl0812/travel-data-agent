from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.agent.llm import llm
from app.prompt.prompt_loader import load_prompt


query = '查询华北地区总销量'

prompt = PromptTemplate(
    template=load_prompt('extend_keywords_for_column_recall'),
    input_variables=['query']
)
output_parser = JsonOutputParser()

chain = prompt | llm | output_parser

result = chain.invoke({'query': query})

print(result)
