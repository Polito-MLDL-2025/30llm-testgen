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


def _read_cli_model(value):
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _first_non_empty(*values):
    for value in values:
        if value:
            return value
    return None


def resolve_qaagent_models(
    cli_model,
    qaagent_model=None,
    qaagent_plan_model=None,
    qaagent_test_model=None,
):
    cli_model = _read_cli_model(cli_model)
    cli_shared_model = _read_cli_model(qaagent_model)
    cli_plan_model = _read_cli_model(qaagent_plan_model)
    cli_test_model = _read_cli_model(qaagent_test_model)
    shared_model = _first_non_empty(
        cli_shared_model,
        cli_model,
        _read_env_model(ENV_QAAGENT_MODEL),
        _read_env_model(ENV_OPENAI_API_MODEL),
    )
    plan_model = _first_non_empty(
        cli_plan_model,
        shared_model,
        _read_env_model(ENV_QAAGENT_PLAN_MODEL),
        DEFAULT_PLAN_MODEL,
    )
    test_model = _first_non_empty(
        cli_test_model,
        shared_model,
        cli_model,
        _read_env_model(ENV_QAAGENT_TEST_MODEL),

    )
    return {
        "plan_model": plan_model,
        "test_model": test_model,
    }


def resolve_merge_models(
    cli_model,
    qaagent_model=None,
    qaagent_plan_model=None,
    qaagent_test_model=None,
    qaagent_merge_model=None,
):
    qaagent_models = resolve_qaagent_models(
        cli_model,
        qaagent_model=qaagent_model,
        qaagent_plan_model=qaagent_plan_model,
        qaagent_test_model=qaagent_test_model,
    )
    cli_shared_model = _read_cli_model(qaagent_model)
    cli_merge_model = _read_cli_model(qaagent_merge_model)
    shared_model = _first_non_empty(
        cli_shared_model,
        _read_env_model(ENV_QAAGENT_MODEL),
        _read_env_model(ENV_OPENAI_API_MODEL),
    )
    merge_model = _first_non_empty(
        cli_merge_model,
        cli_shared_model,
        shared_model,
        _read_env_model(ENV_QAAGENT_MERGE_MODEL),
        qaagent_models["test_model"],
    )
    return {
        "plan_model": qaagent_models["plan_model"],
        "test_model": qaagent_models["test_model"],
        "merge_model": merge_model,
    }


def resolve_competitive_models(
    cli_model,
    qaagent_model=None,
    qaagent_plan_model=None,
    qaagent_test_model=None,
    qaagent_judge_model=None,
):
    qaagent_models = resolve_qaagent_models(
        cli_model,
        qaagent_model=qaagent_model,
        qaagent_plan_model=qaagent_plan_model,
        qaagent_test_model=qaagent_test_model,
    )
    cli_shared_model = _read_cli_model(qaagent_model)
    cli_judge_model = _read_cli_model(qaagent_judge_model)
    shared_model = _first_non_empty(
        cli_shared_model,
        _read_env_model(ENV_QAAGENT_MODEL),
        _read_env_model(ENV_OPENAI_API_MODEL),
    )
    judge_model = _first_non_empty(
        cli_judge_model,
        cli_shared_model,
        shared_model,
        _read_env_model(ENV_QAAGENT_JUDGE_MODEL),
        qaagent_models["test_model"],
    )
    return {
        "plan_model": qaagent_models["plan_model"],
        "test_model": qaagent_models["test_model"],
        "judge_model": judge_model,
    }
