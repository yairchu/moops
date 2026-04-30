from examples import name_casing

import moops


def test_run_returns_result():
    result = moops.run(name_casing, input_text="Hello World", style="snake_case")
    assert result == "hello_world"


def test_run_default_values():
    result = moops.run(name_casing)
    assert result == "lorem_ipsum"
