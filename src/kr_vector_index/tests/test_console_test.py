from kr_vector_index.console_test import TEST_VECTOR_KEY, build_float32_vector, build_query_vector, build_test_vectors


def test_build_test_vectors_matches_s3vectors_shape() -> None:
    vectors = build_test_vectors(dimension=4)

    assert vectors == [
        {
            "key": TEST_VECTOR_KEY,
            "data": {"float32": [0.5, 0.25, 0.125, 0.0625]},
            "metadata": {
                "country": "KR",
                "entity_type": "console_test",
                "city_id": "KR-ConsoleTest",
                "theme_tags": ["console_test"],
                "raw_s3_uri": "s3://console-test/not-persisted.json",
                "ddb_pk": "CONSOLE#TEST",
                "ddb_sk": "VECTOR#TEST",
                "embedding_model": "manual-console-test",
            },
        }
    ]


def test_build_query_vector_uses_same_nonzero_vector() -> None:
    query_vector = build_query_vector(dimension=4)

    assert query_vector == {"float32": [0.5, 0.25, 0.125, 0.0625]}


def test_build_float32_vector_supports_default_index_dimension() -> None:
    vector = build_float32_vector(dimension=1024)

    assert len(vector) == 1024
    assert vector[0] == 0.5
    assert vector[-1] > 0


def test_console_test_module_has_no_delete_vector_command() -> None:
    import inspect
    import kr_vector_index.console_test as console_test

    source = inspect.getsource(console_test)

    assert "delete-vectors" not in source
