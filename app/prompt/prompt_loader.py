from pathlib import Path


def load_prompt(prompt_file_name: str) -> str:

    prompt_path = Path(__file__).parents[2] / "prompts" / f"{prompt_file_name}.prompt"

    return prompt_path.read_text(encoding="utf-8")
