import os

DEFAULT_PLAN_MODEL = "meta/llama3-8b-instruct"

ENV_OPENAI_API_MODEL = "OPENAI_API_MODEL"
ENV_QAAGENT_MODEL = "QAAGENT_MODEL"
ENV_QAAGENT_PLAN_MODEL = "QAAGENT_PLAN_MODEL"
ENV_QAAGENT_TEST_MODEL = "QAAGENT_TEST_MODEL"
ENV_QAAGENT_JUDGE_MODEL = "QAAGENT_JUDGE_MODEL"
ENV_QAAGENT_MERGE_MODEL = "QAAGENT_MERGE_MODEL"


def _read_env_model(env_name):
    value = os.getenv(env_name)
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _first_non_empty(*values):
    for value in values:
        if value:
            return value
    return None


def resolve_qaagent_models(cli_model):
    shared_model = _first_non_empty(
        _read_env_model(ENV_QAAGENT_MODEL),
        _read_env_model(ENV_OPENAI_API_MODEL),
    )
    plan_model = _first_non_empty(
        _read_env_model(ENV_QAAGENT_PLAN_MODEL),
        shared_model,
        DEFAULT_PLAN_MODEL,
    )
    test_model = _first_non_empty(
        _read_env_model(ENV_QAAGENT_TEST_MODEL),
        shared_model,
        cli_model,
    )
    return {
        "plan_model": plan_model,
        "test_model": test_model,
    }


def resolve_merge_models(cli_model):
    qaagent_models = resolve_qaagent_models(cli_model)
    shared_model = _first_non_empty(
        _read_env_model(ENV_QAAGENT_MODEL),
        _read_env_model(ENV_OPENAI_API_MODEL),
    )
    merge_model = _first_non_empty(
        _read_env_model(ENV_QAAGENT_MERGE_MODEL),
        shared_model,
        qaagent_models["test_model"],
    )
    return {
        "plan_model": qaagent_models["plan_model"],
        "test_model": qaagent_models["test_model"],
        "merge_model": merge_model,
    }


def resolve_competitive_models(cli_model):
    qaagent_models = resolve_qaagent_models(cli_model)
    shared_model = _first_non_empty(
        _read_env_model(ENV_QAAGENT_MODEL),
        _read_env_model(ENV_OPENAI_API_MODEL),
    )
    judge_model = _first_non_empty(
        _read_env_model(ENV_QAAGENT_JUDGE_MODEL),
        shared_model,
        qaagent_models["test_model"],
    )
    return {
        "plan_model": qaagent_models["plan_model"],
        "test_model": qaagent_models["test_model"],
        "judge_model": judge_model,
    }
