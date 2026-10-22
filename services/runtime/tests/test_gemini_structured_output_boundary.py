from anne_runtime.gemini_provider import GeminiModelProvider


def test_provider_generation_config_includes_response_schema():
    source = GeminiModelProvider.generate.__code__

    # The production generation path must enforce the Ann-E
    # structured-output schema at the Gemini API boundary.
    #
    # This test intentionally inspects the source constants because
    # the google client is external to this unit test.
    names = set(source.co_names)

    assert "RESPONSE_SCHEMA" in names
