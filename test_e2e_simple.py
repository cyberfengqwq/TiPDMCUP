"""
简化版端到端测试脚本
跳过意图识别模型，直接测试核心功能
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.agent.pipeline import Agent
from core.services.vllm_service import TransformersLLM

print("=" * 60)
print("TiPDMCUP 端到端测试")
print("=" * 60)

SQL_MODEL = "/home/qwq/TiPDMCUP/models/Qwen2.5-7B-N2SQL"
ANALYSIS_MODEL = "/home/qwq/TiPDMCUP/models/Qwen2.5-7B-Coder-Instruct"

print("\n[1/4] 加载SQL生成模型...")
sql_llm = TransformersLLM(
    _modelpath=SQL_MODEL,
    _temperature=0.2,
    _top_p=0.9,
    _max_tokens=512,
)

print("\n[2/4] 加载分析模型...")
analysis_llm = TransformersLLM(
    _modelpath=ANALYSIS_MODEL,
    _temperature=0.7,
    _top_p=0.8,
    _max_tokens=512,
)

print("\n[3/4] 创建Agent（跳过意图识别）...")
agent = Agent(
    user_id="test_user",
    company_id="test_company",
    chat_id="test_chat_001",
    sql_llm=sql_llm,
    analysis_llm=analysis_llm,
    skip_gatekeeper=True,
)

print("\n[4/4] 开始测试...\n")

test_cases = [
    {
        "name": "任务二 - 基本查询",
        "question": "云南白药2024年的净利润是多少",
        "problem_id": "B1001",
        "task": 2,
    },
    {
        "name": "任务二 - 趋势查询",
        "question": "华润三九近几年的利润总额变化趋势是什么样的",
        "problem_id": "B1002",
        "task": 2,
    },
    {
        "name": "任务三 - 多意图查询",
        "question": "2024年利润最高的top10企业是哪些？这些企业的利润、销售额年同比是多少？",
        "problem_id": "B2001",
        "task": 3,
    },
]

for i, tc in enumerate(test_cases, 1):
    print(f"\n{'='*60}")
    print(f"测试 {i}: {tc['name']}")
    print(f"问题: {tc['question']}")
    print("-" * 60)
    
    try:
        result = agent.run(
            question=tc["question"],
            problem_id=tc["problem_id"],
            task=tc["task"],
        )
        
        answer = result.get("A", {})
        
        print(f"\n✅ 测试成功!")
        print(f"\n📝 分析结果:")
        content = answer.get("content", "")
        print(content[:500] + "..." if len(content) > 500 else content)
        
        print(f"\n📊 生成的SQL:")
        print(answer.get("sql", "无"))
        
        print(f"\n📈 图表:")
        images = answer.get("image", [])
        if images:
            for img in images:
                print(f"  - {img}")
        else:
            print("  无图表")
        
        print(f"\n🔗 引用来源:")
        refs = answer.get("references", [])
        if refs:
            for ref in refs[:3]:
                ref_type = ref.get("type", "unknown")
                if ref_type == "provenance":
                    print(f"  - [溯源] {ref.get('stock_abbr', '')} - {ref.get('metric_alias', '')}")
                elif ref_type == "report":
                    print(f"  - [研报] {ref.get('paper_path', '').split('/')[-1]}")
        else:
            print("  无引用")
            
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

print(f"\n{'='*60}")
print("测试完成!")
print("=" * 60)
