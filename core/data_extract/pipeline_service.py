"""
Pipeline 类接口。

将 extract.py / pipeline.py 的所有功能封装为可实例化的类，
通过方法调用代替命令行执行。

用法示例：

    from core.data_extract.pipeline_service import Pipeline

    p = Pipeline(
        model_path="/home/qwq/models/qwen2_5_7b",
        workspace="/data/extract_workspace",
    )
    p.prepare("/data/root_o", execute=True)
    p.screen()
    p.rebuild()
    p.extract()

    # 或一次性跑全流程：
    p.run_all("/data/root_o", execute_prepare=True)
"""

import sys
from pathlib import Path

# 保证同目录下的裸模块名（pipeline、chunk_blocks 等）可以被 import
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from extract import (  # noqa: E402
    DEFAULT_EXTRACT_SCHEMA_TEXT,
    DEFAULT_SCREEN_RULE_TEXT,
    ensure_dirs,
    resolve_workspace_paths,
    run_all,
)
from pipeline import (  # noqa: E402
    run_extract,
    run_prepare,
    run_rebuild,
    run_screen,
)


class Pipeline:
    """
    财报数据提取全流程的类接口。

    Args:
        model_path:              vLLM 模型路径或模型名
        workspace:               流程工作目录（所有中间产物都放在这里）
        screen_rule_text:        初筛规则文本
        extract_schema_text:     细筛抽取 schema 文本
        char_limit:              分块字数阈值
        temperature:             采样温度
        top_p:                   top-p
        screen_max_tokens:       初筛最大输出 token 数
        extract_max_tokens:      细筛最大输出 token 数
        gpu_memory_utilization:  显存占用比例
        separator:               rebuild 时 chunk 断号插入的分隔线
    """

    def __init__(
        self,
        model_path: str,
        workspace: str = "extract_workspace",
        screen_rule_text: str = DEFAULT_SCREEN_RULE_TEXT,
        extract_schema_text: str = DEFAULT_EXTRACT_SCHEMA_TEXT,
        char_limit: int = 6000,
        temperature: float = 0.1,
        top_p: float = 0.8,
        screen_max_tokens: int = 32,
        screen_batch_size: int = 256,
        extract_max_tokens: int = 8192,
        gpu_memory_utilization: float = 0.63,
        separator: str = "\n---\n",
        extract_max_model_len: int | None = 28000,
        extract_batch_size: int = 4,
        split_output_reserve: int | None = None,
        skip_existing: bool = True,
        tensor_parallel_size: int = 1,
    ) -> None:
        self.model_path = model_path
        self.workspace = Path(workspace).resolve()
        self.screen_rule_text = screen_rule_text
        self.extract_schema_text = extract_schema_text
        self.char_limit = char_limit
        self.temperature = temperature
        self.top_p = top_p
        self.screen_max_tokens = screen_max_tokens
        self.screen_batch_size = screen_batch_size
        self.extract_max_tokens = extract_max_tokens
        self.gpu_memory_utilization = gpu_memory_utilization
        self.separator = separator
        self.extract_max_model_len = extract_max_model_len
        self.extract_batch_size = extract_batch_size
        self.split_output_reserve = split_output_reserve
        self.skip_existing = skip_existing
        self.tensor_parallel_size = tensor_parallel_size

    @property
    def paths(self) -> dict[str, Path]:
        return resolve_workspace_paths(self.workspace)

    # ── 单步接口 ──────────────────────────────────────────────────────────────

    def prepare(self, root_o: str, execute: bool = False) -> None:
        """
        从 root_o 中提取 JSON，分块，生成 manifest。

        Args:
            root_o:   原始总目录，下面包含很多子文档目录
            execute:  False=dry-run 预览，True=实际执行移动和删除
        """
        paths = self.paths
        ensure_dirs(self.workspace, paths["collected_json"], paths["waiting_chunk"])
        run_prepare(
            root_o=Path(root_o).resolve(),
            extracted_json_root=paths["collected_json"],
            waiting_chunk_root=paths["waiting_chunk"],
            manifest_file=paths["manifest_file"],
            char_limit=self.char_limit,
            dry_run=not execute,
        )

    def screen(self, doc_filter: list[str] | None = None) -> None:
        """
        将 waiting_chunk 转成 markdown，用模型做初筛，
        把 YES 的 chunk 写入 new_chunk。

        Args:
            doc_filter: 只处理指定 doc_id 列表，None 表示全部处理
        """
        paths = self.paths
        ensure_dirs(self.workspace, paths["waiting_markdown"], paths["new_chunk"])
        run_screen(
            waiting_chunk_root=paths["waiting_chunk"],
            waiting_markdown_root=paths["waiting_markdown"],
            new_chunk_root=paths["new_chunk"],
            results_file=paths["screen_results"],
            model_path=self.model_path,
            rule_text=self.screen_rule_text,
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.screen_max_tokens,
            gpu_memory_utilization=self.gpu_memory_utilization,
            doc_filter=doc_filter,
            screen_batch_size=self.screen_batch_size,
        )

    def rebuild(self) -> None:
        """
        遍历 new_chunk，重组筛选后的 chunk 为 extracted_data markdown。
        """
        paths = self.paths
        ensure_dirs(self.workspace, paths["extracted_data"])
        run_rebuild(
            new_chunk_root=paths["new_chunk"],
            extracted_data_root=paths["extracted_data"],
            separator=self.separator,
        )

    def extract(self) -> None:
        """
        对 extracted_data markdown 做细筛抽取，输出 extracted_json。
        """
        paths = self.paths
        ensure_dirs(self.workspace, paths["extracted_json"])
        run_extract(
            extracted_data_root=paths["extracted_data"],
            extracted_json_root=paths["extracted_json"],
            results_file=paths["extract_results"],
            model_path=self.model_path,
            schema_text=self.extract_schema_text,
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.extract_max_tokens,
            gpu_memory_utilization=self.gpu_memory_utilization,
            max_model_len=self.extract_max_model_len,
            extract_batch_size=self.extract_batch_size,
            separator=self.separator,
            split_output_reserve=self.split_output_reserve,
            skip_existing=self.skip_existing,
            tensor_parallel_size=self.tensor_parallel_size,
        )

    # ── 全流程接口 ────────────────────────────────────────────────────────────

    def run_all(self, root_o: str, execute_prepare: bool = False) -> None:
        """
        一次性运行完整流程：prepare → screen → rebuild → extract。

        Args:
            root_o:           原始总目录
            execute_prepare:  False=dry-run，True=实际执行提取和删除
        """
        run_all(
            root_o=Path(root_o).resolve(),
            workspace=self.workspace,
            model_path=self.model_path,
            screen_rule_text=self.screen_rule_text,
            extract_schema_text=self.extract_schema_text,
            char_limit=self.char_limit,
            temperature=self.temperature,
            top_p=self.top_p,
            screen_max_tokens=self.screen_max_tokens,
            extract_max_tokens=self.extract_max_tokens,
            gpu_memory_utilization=self.gpu_memory_utilization,
            execute_prepare=execute_prepare,
            separator=self.separator,
        )
