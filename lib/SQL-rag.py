from langchain_community.vectorstores import Chroma
from langchain_core.prompts import (
    FewShotPromptTemplate,
    PromptTemplate,
    SemanticSimilarityExampleSelector,
)
from langchain_huggingface import HuggingFaceEmbeddings

# 1. 准备你的标准 SQL 题库 (Few-shot 样本池)
examples = [
    {
        "question": "金花股份近几年的利润总额变化趋势是什么样的",
        "query": "SELECT report_period, total_profit FROM income_sheet WHERE stock_abbr = '金花股份' ORDER BY report_period;",
    },
    {
        "question": "2024年利润最高的top10企业是哪些",
        "query": "SELECT stock_abbr, total_profit FROM income_sheet WHERE report_period LIKE '2024%' ORDER BY total_profit DESC LIMIT 10;",
    },
    # ... 在这里多准备一些比赛要求的高频复杂句式
]

# 2. 初始化你的本地 4060 Embedding 模型
embeddings = HuggingFaceEmbeddings(
    model_name="BAAI/bge-m3", model_kwargs={"device": "cuda"}
)

# 3. 构造动态检索器 (SQL RAG 核心)
example_selector = SemanticSimilarityExampleSelector.from_examples(
    examples,
    embeddings,
    Chroma,
    k=2,  # 每次大模型写 SQL 前，自动找出最相似的 2 个例子给它抄
)

# 4. 组装发给大模型 API 的终极 Prompt
example_prompt = PromptTemplate(
    input_variables=["question", "query"],
    template="用户问题: {question}\n标准SQL: {query}",
)

dynamic_prompt = FewShotPromptTemplate(
    example_selector=example_selector,
    example_prompt=example_prompt,
    prefix="你是一个资深MySQL DBA。请参考以下相似历史经验，为用户的新问题生成准确的SQL语句：\n【参考经验】",
    suffix="\n【当前任务】\n用户问题: {input}\n生成的SQL:",
    input_variables=["input"],
)

# 当用户问一个新问题时：
new_question = "华润三九近几年的利润趋势是怎样的？"
print(dynamic_prompt.format(input=new_question))

# 此时你会发现，打印出的 prompt 里面自动带上了 "金花股份近几年的利润..." 那个例子！
# 大模型拿到这个 prompt，生成的 SQL 绝对不会出错。
