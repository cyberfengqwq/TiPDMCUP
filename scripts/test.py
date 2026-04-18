from core.data_extract.pipeline_service import Pipeline

def main() -> None:
    pipline = Pipeline(
        model_path="/home/qwq/models/Qwen3-8B",
        workspace="core/data_extract/extract_workspace",
        gpu_memory_utilization=0.85,
        extract_max_model_len=40960,
        extract_max_tokens=16384,
        split_output_reserve=16384,
        extract_batch_size=32,        # 批量提交，充分利用 A100
        tensor_parallel_size=4,
    )
    # pipline.screen(doc_filter=["600080_"])
    # pipline.rebuild()  # 重组 new_chunk → extracted_data markdown
    pipline.extract()  # LLM 细筛抽取 → extracted_json


if __name__ == "__main__":
    main()
