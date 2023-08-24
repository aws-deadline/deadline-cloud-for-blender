# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any, Generator
from unittest.mock import Mock, patch

import deadline.client.api
import boto3  # type: ignore
import moto  # type: ignore
import pytest
from deadline_test_scaffolding.deadline_stub import (
    FarmInfo,
    QueueInfo,
    StubDeadlineClient,
)

from deadline_submitter_for_blender.utilities import utility_functions


@pytest.fixture(autouse=True)
def moto_mocks() -> Generator[None, None, None]:
    with moto.mock_s3(), moto.mock_sts():
        yield


@pytest.fixture(autouse=True)
def job_attachments_bucket(moto_mocks) -> Any:
    s3: Any = boto3.resource("s3")
    bucket = s3.Bucket("test-job-attachments-bucket")
    bucket.create(
        CreateBucketConfiguration={"LocationConstraint": "us-west-2"},
    )
    return bucket


@pytest.fixture
def stub_deadline_client(job_attachments_bucket: Any) -> StubDeadlineClient:
    return StubDeadlineClient(
        farm=FarmInfo("test-farm-name"),
        queue=QueueInfo("test-queue-name"),
        job_attachments_bucket_name=job_attachments_bucket.name,
    )


@pytest.fixture(autouse=True)
def mock_deadline_get_client(
    stub_deadline_client: StubDeadlineClient,
) -> Generator[Mock, None, None]:
    with patch.object(
        deadline.client.api, "get_boto3_client", return_value=stub_deadline_client
    ) as mock:
        yield mock


def test_get_farms(stub_deadline_client):
    # WHEN
    result = utility_functions.get_farms()

    # THEN
    farm_id, farm_name, *rest = result[0]
    assert farm_id == stub_deadline_client.farm.farmId
    assert farm_name == stub_deadline_client.farm.name


def test_get_queues(stub_deadline_client):
    # WHEN
    result = utility_functions.get_queues(stub_deadline_client.farm.farmId)

    # THEN
    queue_id, queue_name, *rest = result[0]
    assert queue_id == stub_deadline_client.queue.queueId
    assert queue_name == stub_deadline_client.queue.name
