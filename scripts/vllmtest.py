from core.services.vllm_service import LLM

llm = LLM(
    _modelpath="/home/qwq/TiPDMCUP/models/base/Qwen2.5-7B-Coder-Instruct",
    _temperature=0.1,
    _top_p=0.8,
    _max_tokens=16,
    _gpu_memory_utilization=0.7,
)

llm.load_model()
print(llm.chat("只回答YES或NO。1+1是否等于2？"))
llm.unload_model()
