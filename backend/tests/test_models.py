import config


def test_aliases_and_families():
    assert config.MODEL_ALIASES["gemma4"].startswith("mlx-community/gemma-4")
    assert config._family("mlx-community/gemma-4-26b-a4b-it-4bit") == "gemma"
    assert config._family("mlx-community/sarvam-m-4bit") == "sarvam"
    assert config._family("mlx-community/Qwen3-14B-4bit") == "qwen"
    assert config.FALLBACK_MODEL.startswith("mlx-community/")
    assert 0 < config.LOCAL_HINDI_TEMPERATURE <= 1
