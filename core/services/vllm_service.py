# core/services/vllm_service.py

import gc
import json
import logging
from pathlib import Path
from typing import Any

import torch
import vllm
from transformers import AutoTokenizer


logger = logging.getLogger(__name__)


def _sanitize_tokenizer_config(model_path: str) -> None:
    """
    兼容部分模型 `tokenizer_config.json` 中 `extra_special_tokens` 的旧格式。

    新版 transformers 在部分 tokenizer 初始化时会假设该字段为 dict，
    若为 list 会触发：'list' object has no attribute 'keys'。
    """
    config_path = Path(model_path) / "tokenizer_config.json"
    if not config_path.exists():
        return

    try:
        data: dict[str, Any] = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("[LLM] 读取 tokenizer_config 失败：%s", e)
        return

    value = data.get("extra_special_tokens")
    if not isinstance(value, list):
        return

    converted: dict[str, str] = {}
    for idx, item in enumerate(value):
        if isinstance(item, str):
            converted[f"extra_special_token_{idx}"] = item
            continue

        if isinstance(item, dict):
            token = item.get("content") or item.get("token") or item.get("text")
            name = item.get("name") or f"extra_special_token_{idx}"
            if isinstance(token, str):
                converted[str(name)] = token

    data["extra_special_tokens"] = converted

    try:
        config_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.warning(
            "[LLM] 检测到旧版 extra_special_tokens(list)，已自动转换为 dict：%s",
            str(config_path),
        )
    except Exception as e:
        logger.warning("[LLM] 写回 tokenizer_config 失败：%s", e)


class LLM:
    """基于 vLLM 的常驻模型（用于意图识别等启动时加载的小模型）"""

    def __init__(
        self,
        _modelpath: str,
        _temperature: float = 0.7,
        _top_p: float = 0.8,
        _max_tokens: int = 512,
        _gpu_memory_utilization: float = 0.63,
        _max_model_len: int = 8192,
        _limit_mm_per_prompt: dict | None = None,
        _enforce_eager: bool = False,
    ) -> None:
        self.model_path: str = _modelpath
        self.temperature: float = _temperature
        self.top_p: float = _top_p
        self.max_tokens: int = _max_tokens
        self.gpu_memory_utilization: float = _gpu_memory_utilization
        self.max_model_len: int = _max_model_len
        self.limit_mm_per_prompt: dict | None = _limit_mm_per_prompt
        self.enforce_eager: bool = _enforce_eager

        self.llm = None
        self.tokenizer = None
        self.sampling_params = None

    def load_model(self) -> None:
        project_root = Path(__file__).resolve().parent.parent
        models_dir = project_root / "models"

        if self.llm is None:
            model_path = str(Path(self.model_path).expanduser().resolve())
            print(f"正在加载模型：{model_path}")
            _sanitize_tokenizer_config(model_path)

            vllm_kwargs: dict = {
                "model": model_path,
                "gpu_memory_utilization": self.gpu_memory_utilization,
                "download_dir": str(models_dir),
                "trust_remote_code": True,
                "quantization": "bitsandbytes",
                "load_format": "bitsandbytes",
                "max_model_len": self.max_model_len,
            }
            if self.limit_mm_per_prompt is not None:
                vllm_kwargs["limit_mm_per_prompt"] = self.limit_mm_per_prompt
            if self.enforce_eager:
                vllm_kwargs["enforce_eager"] = True
            self.llm = vllm.LLM(**vllm_kwargs)

            self.tokenizer = AutoTokenizer.from_pretrained(
                model_path,
                trust_remote_code=True,
            )
            self.sampling_params = vllm.SamplingParams(
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
            )
            print("模型加载完成")
        else:
            print("模型已经在运行中")

    def unload_model(self) -> None:
        if self.llm is not None:
            print("正在关闭模型")
            del self.llm
            self.llm = None
            if self.tokenizer:
                del self.tokenizer
                self.tokenizer = None
            self.sampling_params = None
            gc.collect()
            torch.cuda.empty_cache()
            print("模型已关闭")
        else:
            print("模型并未启动")

    @property
    def get_model_status(self) -> bool:
        return self.llm is not None

    def chat(self, text: str) -> str:
        if self.tokenizer is None or self.llm is None:
            print("模型未启动")
            return ""

        messages = [{"role": "user", "content": text}]
        prompt_text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        response = self.llm.generate([prompt_text], self.sampling_params)
        return str(response[0].outputs[0].text)

    def set_sampling_params(
        self, _temperature: float, _top_p: float, _max_tokens: int
    ) -> None:
        self.temperature = _temperature
        self.top_p = _top_p
        self.max_tokens = _max_tokens
        if self.sampling_params:
            self.sampling_params = vllm.SamplingParams(
                temperature=self.temperature,
                top_p=self.top_p,
                max_tokens=self.max_tokens,
            )

    def __del__(self) -> None:
        if self.llm:
            del self.llm
            torch.cuda.empty_cache()


class TransformersLLM:
    """
    基于 transformers + bitsandbytes 的按需加载模型。
    不使用 vLLM 子进程，避免 CUDA 已初始化后 spawn 死锁问题。
    适用于 SQL 生成、财报分析等按需加载/卸载的大模型。
    """

    def __init__(
        self,
        _modelpath: str,
        _temperature: float = 0.7,
        _top_p: float = 0.8,
        _max_tokens: int = 512,
    ) -> None:
        self.model_path = _modelpath
        self.temperature = _temperature
        self.top_p = _top_p
        self.max_tokens = _max_tokens
        self.model = None
        self.tokenizer = None

    def load_model(self) -> None:
        if self.model is not None:
            print("模型已经在运行中")
            return

        from transformers import AutoModelForCausalLM, BitsAndBytesConfig

        model_path = str(Path(self.model_path).expanduser().resolve())
        print(f"正在加载模型：{model_path}")
        _sanitize_tokenizer_config(model_path)

        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            quantization_config=bnb_config,
            device_map="cuda",
            trust_remote_code=True,
        )
        self.model.eval()
        print("模型加载完成")

    def unload_model(self) -> None:
        if self.model is not None:
            print("正在关闭模型")
            del self.model
            self.model = None
            if self.tokenizer is not None:
                del self.tokenizer
                self.tokenizer = None
            gc.collect()
            torch.cuda.empty_cache()
            print("模型已关闭")
        else:
            print("模型并未启动")

    @property
    def get_model_status(self) -> bool:
        return self.model is not None

    def chat(self, text: str) -> str:
        if self.model is None or self.tokenizer is None:
            print("模型未启动")
            return ""

        messages = [{"role": "user", "content": text}]
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to("cuda")

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_tokens,
                temperature=self.temperature if self.temperature > 0 else None,
                top_p=self.top_p if self.temperature > 0 else None,
                do_sample=self.temperature > 0,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True)

    def set_sampling_params(
        self, _temperature: float, _top_p: float, _max_tokens: int
    ) -> None:
        self.temperature = _temperature
        self.top_p = _top_p
        self.max_tokens = _max_tokens

    def __del__(self) -> None:
        if self.model:
            del self.model
            torch.cuda.empty_cache()
