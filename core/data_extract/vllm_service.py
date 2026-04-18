# core/services/vllm_service.py

from pathlib import Path

import torch
import vllm
from transformers import AutoTokenizer


class LLM:
    def __init__(
        self,
        _modelpath: str,
        _temperature: float = 0.7,
        _top_p: float = 0.8,
        _max_tokens: int = 512,
        _gpu_memory_utilization: float = 0.63,
        _enable_thinking: bool = True,
        _max_model_len: int | None = None,
        _tensor_parallel_size: int = 1,
    ) -> None:
        """
        初始化 LLM 配置
        """
        self.model_path: str = _modelpath
        self.temperature: float = _temperature
        self.top_p: float = _top_p
        self.max_tokens: int = _max_tokens  # 最大回复长度
        self.gpu_memory_utilization: float = _gpu_memory_utilization  # 显存占用率
        self.enable_thinking: bool = _enable_thinking
        self.max_model_len: int | None = _max_model_len
        self.tensor_parallel_size: int = _tensor_parallel_size

        self.llm = None
        self.tokenizer = None
        self.sampling_params = None

    def load_model(self) -> None:
        """
        新增接口：启动配置的 LLM 模型
        """
        # 找到模型的存储路径
        project_root = Path(__file__).resolve().parent.parent
        models_dir = project_root / "models"

        if self.llm is None:
            model_path = str(Path(self.model_path).expanduser().resolve())
            print(f"正在加载模型：{model_path}")

            # 使用 vLLM 加载模型
            self.llm = vllm.LLM(
                model=model_path,
                gpu_memory_utilization=self.gpu_memory_utilization,
                download_dir=str(models_dir),
                trust_remote_code=True,
                max_model_len=self.max_model_len,
                enable_prefix_caching=True,
                tensor_parallel_size=self.tensor_parallel_size,
            )

            # 加载分词器
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)

            # 模型参数设置：选词方式
            self.sampling_params = vllm.SamplingParams(
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
            )
            print("模型加载完成")
        else:
            print("模型已经在运行中")

    def unload_model(self) -> None:
        """
        新增接口：关闭模型
        """
        if self.llm is not None:
            print("正在关闭模型")
            del self.llm
            self.llm = None

            if self.tokenizer:
                del self.tokenizer
                self.tokenizer = None

            torch.cuda.empty_cache()
            print("模型已关闭")
        else:
            print("模型并未启动")

    @property
    def get_model_status(self) -> bool:
        return self.llm is not None

    def chat(self, text: str) -> str:
        """
        用来产出对话

        Args:
            text: 输入文本

        Returns:
            answer_text: llm回复
        """
        if self.tokenizer is None or self.llm is None:
            print("模型未启动")
            return ""

        assert self.tokenizer is not None
        assert self.llm is not None

        # AI 对话的标准格式：系统指令 + 用户提问
        messages = [
            {"role": "user", "content": text},
        ]

        # 把 messages 列表转成模型能看懂的格式
        prompt_text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
            enable_thinking=self.enable_thinking,
        )

        # 生成回答
        response = self.llm.generate([prompt_text], self.sampling_params)

        # 提取回答中的文字
        answer_text: str = str(response[0].outputs[0].text)
        return str(answer_text)

    def batch_chat(self, texts: list[str], batch_size: int = 200) -> list[str]:
        """
        批量推理，分批提交避免 KV cache 溢出触发 preemption。

        Args:
            texts:      输入文本列表
            batch_size: 每批最多提交多少条（默认 200，可按显存调整）

        Returns:
            与输入顺序对应的回复列表
        """
        if self.tokenizer is None or self.llm is None:
            print("模型未启动")
            return [""] * len(texts)

        max_input_len = (self.max_model_len - self.max_tokens) if self.max_model_len else None

        all_results: list[str] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start: start + batch_size]
            prompt_texts = []
            for text in batch:
                # 先用空 template 估算非内容部分的 token 开销，再按比例截断内容
                if max_input_len is not None:
                    content_ids = self.tokenizer.encode(text, add_special_tokens=False)
                    overhead = max_input_len - len(content_ids)  # 粗略估算 template 开销
                    if overhead < 200:  # template 大概 50-100 token，至少留 200 余量
                        keep = max(0, max_input_len - 200)
                        content_ids = content_ids[:keep]
                        text = self.tokenizer.decode(content_ids, skip_special_tokens=True)
                token_ids = self.tokenizer.apply_chat_template(
                    [{"role": "user", "content": text}],
                    tokenize=True,
                    add_generation_prompt=True,
                    enable_thinking=self.enable_thinking,
                )
                if max_input_len and len(token_ids) > max_input_len:
                    token_ids = token_ids[:max_input_len]
                prompt_texts.append({"prompt_token_ids": token_ids})
            responses = self.llm.generate(prompt_texts, self.sampling_params)
            all_results.extend(str(r.outputs[0].text) for r in responses)
            print(f"  批次完成 {min(start + batch_size, len(texts))}/{len(texts)}")
        return all_results

    def set_sampling_params(
        self, _temperature: float, _top_p: float, _max_tokens: int
    ) -> None:
        """
        这个函数用来调整模型采样参数
        """
        self.temperature = _temperature
        self.top_p = _top_p
        self.max_tokens = _max_tokens
        if self.sampling_params:
            self.sampling_params = vllm.SamplingParams(
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
            )

    def set_gpu_memory_utilization(self, gpu_memory_utilization: float) -> None:
        if self.llm is None:
            self.gpu_memory_utilization = gpu_memory_utilization
        else:
            self.unload_model()
            self.gpu_memory_utilization = gpu_memory_utilization
            self.load_model()

    def __del__(self) -> None:
        """
        析构函数: 删除实例对象后清理显存
        """
        if self.llm:
            del self.llm
            torch.cuda.empty_cache()
