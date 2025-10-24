import io
from unittest import mock

from django.core.management.base import CommandError

import pandas as pd
import pytest

from basket.news.management.commands.process_braze_external_id_migrator import Command


@pytest.fixture
def sample_df():
    return pd.DataFrame(
        [
            {"email_id": "id1", "basket_token": "token1", "create_timestamp": "2024-01-01T00:00:00"},
            {"email_id": "id2", "basket_token": "token2", "create_timestamp": "2024-02-01T00:00:00"},
        ]
    )


def parquet_bytes(df):
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    buf.seek(0)
    return buf.read()


@pytest.fixture(autouse=True)
def mock_braze():
    with mock.patch("basket.news.management.commands.process_braze_external_id_migrator.braze") as braze_mock:
        yield braze_mock


@pytest.fixture(autouse=True)
def mock_storage_client():
    with mock.patch("basket.news.management.commands.process_braze_external_id_migrator.storage.Client") as storage_mock:
        yield storage_mock


def test_successful_migration(mock_storage_client, mock_braze, sample_df):
    mock_blob = mock.Mock()
    mock_blob.exists.return_value = True
    mock_blob.download_as_bytes.return_value = parquet_bytes(sample_df)
    mock_bucket = mock.Mock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = mock.Mock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage_client.return_value = mock_client

    mock_braze.migrate_external_id.return_value = {"braze_collected_response": {"external_ids": ["id1", "id2"], "rename_errors": []}}

    cmd = Command()
    cmd.stdout = mock.Mock()
    cmd.process_and_migrate_parquet_file(
        project="proj", bucket="bucket", prefix="prefix", file_name="file.parquet", start_timestamp=None, chunk_size=2
    )
    expected_chunk = [
        {"current_external_id": "id1", "new_external_id": "token1"},
        {"current_external_id": "id2", "new_external_id": "token2"},
    ]
    mock_braze.migrate_external_id.assert_called_once_with(expected_chunk)


def test_file_not_found(mock_storage_client, mock_braze):
    mock_blob = mock.Mock()
    mock_blob.exists.return_value = False
    mock_bucket = mock.Mock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = mock.Mock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage_client.return_value = mock_client

    cmd = Command()
    with pytest.raises(CommandError) as exc:
        cmd.process_and_migrate_parquet_file(
            project="proj", bucket="bucket", prefix="prefix", file_name="file.parquet", start_timestamp=None, chunk_size=2
        )
    assert "not found" in str(exc.value)


def test_migration_failure(mock_storage_client, mock_braze, sample_df):
    mock_blob = mock.Mock()
    mock_blob.exists.return_value = True
    mock_blob.download_as_bytes.return_value = parquet_bytes(sample_df)
    mock_bucket = mock.Mock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = mock.Mock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage_client.return_value = mock_client

    mock_braze.migrate_external_id.side_effect = Exception("fail!")
    cmd = Command()
    cmd.stdout = mock.Mock()
    cmd.style = mock.Mock()
    cmd.style.ERROR = lambda x: x
    with pytest.raises(CommandError) as exc:
        cmd.process_and_migrate_parquet_file(
            project="proj", bucket="bucket", prefix="prefix", file_name="file.parquet", start_timestamp=None, chunk_size=2
        )
    assert "Migration failed" in str(exc.value)
    assert any("fail!" in str(call_arg[0][0]) for call_arg in cmd.stdout.write.call_args_list)


def test_start_timestamp_filtering(mock_storage_client, mock_braze):
    df = pd.DataFrame(
        [
            {"email_id": "id1", "basket_token": "token1", "create_timestamp": "2023-01-01T00:00:00"},
            {"email_id": "id2", "basket_token": "token2", "create_timestamp": "2024-02-01T00:00:00"},
        ]
    )
    mock_blob = mock.Mock()
    mock_blob.exists.return_value = True
    mock_blob.download_as_bytes.return_value = parquet_bytes(df)
    mock_bucket = mock.Mock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = mock.Mock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage_client.return_value = mock_client

    cmd = Command()
    cmd.stdout = mock.Mock()
    cmd.process_and_migrate_parquet_file(
        project="proj", bucket="bucket", prefix="prefix", file_name="file.parquet", start_timestamp="2024-01-01T00:00:00", chunk_size=2
    )
    expected_chunk = [{"current_external_id": "id2", "new_external_id": "token2"}]
    mock_braze.migrate_external_id.assert_called_once_with(expected_chunk)


def test_empty_parquet_file(mock_storage_client, mock_braze):
    empty_df = pd.DataFrame(columns=["email_id", "basket_token", "create_timestamp"])
    mock_blob = mock.Mock()
    mock_blob.exists.return_value = True
    mock_blob.download_as_bytes.return_value = parquet_bytes(empty_df)
    mock_bucket = mock.Mock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = mock.Mock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage_client.return_value = mock_client

    cmd = Command()
    cmd.stdout = mock.Mock()
    cmd.process_and_migrate_parquet_file(
        project="proj", bucket="bucket", prefix="prefix", file_name="file.parquet", start_timestamp=None, chunk_size=2
    )
    mock_braze.migrate_external_id.assert_not_called()


def test_chunking_behavior(mock_storage_client, mock_braze):
    df = pd.DataFrame([{"email_id": f"id{i}", "basket_token": f"token{i}", "create_timestamp": f"2024-01-01T00:00:0{i}"} for i in range(5)])
    mock_blob = mock.Mock()
    mock_blob.exists.return_value = True
    mock_blob.download_as_bytes.return_value = parquet_bytes(df)
    mock_bucket = mock.Mock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = mock.Mock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage_client.return_value = mock_client

    cmd = Command()
    cmd.stdout = mock.Mock()
    cmd.process_and_migrate_parquet_file(
        project="proj", bucket="bucket", prefix="prefix", file_name="file.parquet", start_timestamp=None, chunk_size=2
    )
    # Should be called 3 times: 2, 2, 1
    assert mock_braze.migrate_external_id.call_count == 3
    all_calls = [call.args[0] for call in mock_braze.migrate_external_id.call_args_list]
    assert all(len(chunk) <= 2 for chunk in all_calls)


@mock.patch("basket.news.management.commands.process_braze_external_id_migrator.time.sleep")
def test_rate_limit_sleep_between_chunks(mock_sleep, sample_df, mock_storage_client, mock_braze):
    mock_blob = mock.Mock()
    mock_blob.exists.return_value = True
    mock_blob.download_as_bytes.return_value = parquet_bytes(sample_df)
    mock_bucket = mock.Mock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = mock.Mock()
    mock_client.bucket.return_value = mock_bucket
    mock_storage_client.return_value = mock_client

    cmd = Command()
    cmd.stdout = mock.Mock()
    cmd.process_and_migrate_parquet_file(
        project="proj", bucket="bucket", prefix="prefix", file_name="file.parquet", start_timestamp=None, chunk_size=1
    )

    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(0.07)
