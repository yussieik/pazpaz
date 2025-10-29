"""Performance baseline tests for PazPaz schedule endpoints.

Tests validate that the backend meets the p95 <150ms requirement specified in
PROJECT_OVERVIEW.md for schedule-related endpoints.

Run with: pytest -m performance -v
"""

from __future__ import annotations

import asyncio
import statistics
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from tests.conftest import add_csrf_to_client, get_auth_headers

pytestmark = [pytest.mark.asyncio, pytest.mark.performance]

# Performance targets from PROJECT_OVERVIEW.md
P95_TARGET_MS = 150  # p95 < 150ms for schedule endpoints
P99_TARGET_MS = 300  # reasonable p99 target
MEAN_TARGET_MS = 100  # reasonable mean target
NUM_ITERATIONS = 100  # number of requests to measure

# Conflict detection specific targets (stricter for real-time UX)
CONFLICT_P95_TARGET_MS = 100  # p95 < 100ms for conflict checks (UX requirement)
CONFLICT_MEAN_TARGET_MS = 50  # mean < 50ms for conflict checks


def percentile(data: list[float], p: float) -> float:
    """
    Calculate percentile of a dataset.

    Args:
        data: List of numeric values
        p: Percentile to calculate (0-100)

    Returns:
        Value at the given percentile
    """
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def calculate_stats(response_times: list[float]) -> dict[str, float]:
    """
    Calculate statistics from response times.

    Args:
        response_times: List of response times in milliseconds

    Returns:
        Dictionary with mean, p95, p99, min, max
    """
    return {
        "mean": statistics.mean(response_times),
        "median": statistics.median(response_times),
        "p95": percentile(response_times, 95),
        "p99": percentile(response_times, 99),
        "min": min(response_times),
        "max": max(response_times),
    }


def format_stats(stats: dict[str, float], dataset_size: str) -> str:
    """
    Format statistics for readable output.

    Args:
        stats: Statistics dictionary from calculate_stats
        dataset_size: Description of dataset size

    Returns:
        Formatted string with statistics
    """
    return (
        f"\n{dataset_size}:\n"
        f"  Mean: {stats['mean']:.2f}ms\n"
        f"  Median: {stats['median']:.2f}ms\n"
        f"  p95: {stats['p95']:.2f}ms\n"
        f"  p99: {stats['p99']:.2f}ms\n"
        f"  Min: {stats['min']:.2f}ms\n"
        f"  Max: {stats['max']:.2f}ms"
    )


async def create_test_clients(
    db_session: AsyncSession, workspace: Workspace, count: int
) -> list[Client]:
    """
    Create multiple test clients for performance testing.

    Args:
        db_session: Database session
        workspace: Workspace to create clients in
        count: Number of clients to create

    Returns:
        List of created clients
    """
    clients = []
    for i in range(count):
        client = Client(
            workspace_id=workspace.id,
            first_name=f"TestClient{i}",
            last_name=f"LastName{i}",
            email=f"testclient{i}@example.com",
            phone=f"+1234567{i:04d}",
            consent_status=True,
            notes=f"Performance test client {i}",
            tags=["performance-test"],
        )
        clients.append(client)
        db_session.add(client)

    await db_session.commit()
    for client in clients:
        await db_session.refresh(client)

    return clients


async def create_test_appointments(
    db_session: AsyncSession,
    workspace: Workspace,
    clients: list[Client],
    count: int,
    start_date: datetime,
) -> list[Appointment]:
    """
    Create multiple test appointments for performance testing.

    Distributes appointments across clients and dates to simulate realistic load.

    Args:
        db_session: Database session
        workspace: Workspace to create appointments in
        clients: List of clients to assign appointments to
        count: Number of appointments to create
        start_date: Base date for scheduling appointments

    Returns:
        List of created appointments
    """
    appointments = []
    for i in range(count):
        # Distribute appointments across clients
        client = clients[i % len(clients)]

        # Distribute appointments across 30 days, various times
        day_offset = i % 30
        hour = 9 + (i % 8)  # Hours 9-16

        scheduled_start = start_date + timedelta(days=day_offset, hours=hour)
        scheduled_end = scheduled_start + timedelta(hours=1)

        # Vary appointment types
        location_types = [LocationType.CLINIC, LocationType.HOME, LocationType.ONLINE]
        location_type = location_types[i % len(location_types)]

        # Vary statuses (mostly scheduled, some attended/cancelled)
        statuses = (
            [AppointmentStatus.SCHEDULED] * 7
            + [AppointmentStatus.ATTENDED] * 2
            + [AppointmentStatus.CANCELLED]
        )
        status = statuses[i % len(statuses)]

        appointment = Appointment(
            workspace_id=workspace.id,
            client_id=client.id,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            location_type=location_type,
            location_details=f"Test location {i}",
            status=status,
            notes=f"Performance test appointment {i}",
        )
        appointments.append(appointment)
        db_session.add(appointment)

    await db_session.commit()
    for appointment in appointments:
        await db_session.refresh(appointment)

    return appointments


@pytest.fixture
async def small_dataset(
    db_session: AsyncSession, workspace_1: Workspace
) -> dict[str, Any]:
    """
    Create small test dataset: 10 clients, 50 appointments.

    Represents a new therapist just starting their practice.
    """
    clients = await create_test_clients(db_session, workspace_1, 10)
    start_date = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=15)
    appointments = await create_test_appointments(
        db_session, workspace_1, clients, 50, start_date
    )
    return {
        "workspace": workspace_1,
        "clients": clients,
        "appointments": appointments,
        "size": "small",
    }


@pytest.fixture
async def medium_dataset(
    db_session: AsyncSession, workspace_1: Workspace
) -> dict[str, Any]:
    """
    Create medium test dataset: 50 clients, 500 appointments.

    Represents an established therapist with moderate client load.
    """
    clients = await create_test_clients(db_session, workspace_1, 50)
    start_date = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=90)
    appointments = await create_test_appointments(
        db_session, workspace_1, clients, 500, start_date
    )
    return {
        "workspace": workspace_1,
        "clients": clients,
        "appointments": appointments,
        "size": "medium",
    }


@pytest.fixture
async def large_dataset(
    db_session: AsyncSession, workspace_1: Workspace, test_user_ws1: User
) -> dict[str, Any]:
    """
    Create large test dataset: 100 clients, 1000 appointments.

    Represents a very busy therapist or small clinic with extensive history.
    """
    clients = await create_test_clients(db_session, workspace_1, 100)
    start_date = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=180)
    appointments = await create_test_appointments(
        db_session, workspace_1, clients, 1000, start_date
    )
    return {
        "workspace": workspace_1,
        "clients": clients,
        "appointments": appointments,
        "size": "large",
    }


@pytest.fixture
async def performance_dataset(
    request: pytest.FixtureRequest,
    db_session: AsyncSession,
    workspace_1: Workspace,
    test_user_ws1: User,
) -> dict[str, Any]:
    """
    Parametrized fixture that provides dataset based on test parameter.

    This fixture eliminates the need for request.getfixturevalue() which
    causes event loop issues with pytest-asyncio.

    Usage:
        @pytest.mark.parametrize(
            "performance_dataset", ["small", "medium", "large"], indirect=True
        )
        async def test_something(performance_dataset):
            dataset = performance_dataset
            # ... use dataset
    """
    size = request.param

    if size == "small":
        clients = await create_test_clients(db_session, workspace_1, 10)
        start_date = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=15)
        appointments = await create_test_appointments(
            db_session, workspace_1, clients, 50, start_date
        )
    elif size == "medium":
        clients = await create_test_clients(db_session, workspace_1, 50)
        start_date = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=90)
        appointments = await create_test_appointments(
            db_session, workspace_1, clients, 500, start_date
        )
    elif size == "large":
        clients = await create_test_clients(db_session, workspace_1, 100)
        start_date = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=180)
        appointments = await create_test_appointments(
            db_session, workspace_1, clients, 1000, start_date
        )
    else:
        raise ValueError(f"Unknown dataset size: {size}")

    return {
        "workspace": workspace_1,
        "clients": clients,
        "appointments": appointments,
        "size": size,
    }


async def measure_endpoint_performance(
    client: AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    iterations: int = NUM_ITERATIONS,
    **kwargs,
) -> list[float]:
    """
    Measure endpoint response times over multiple iterations.

    Args:
        client: HTTP test client
        method: HTTP method (get, post, etc.)
        url: Endpoint URL
        headers: Request headers
        iterations: Number of requests to measure
        **kwargs: Additional arguments for the request

    Returns:
        List of response times in milliseconds
    """
    response_times = []
    client_method = getattr(client, method.lower())

    for _ in range(iterations):
        start = time.perf_counter()
        response = await client_method(url, headers=headers, **kwargs)
        end = time.perf_counter()

        # Verify successful response
        assert response.status_code in {200, 201, 204}, (
            f"Request failed: {response.status_code} - {response.text}"
        )

        response_times.append((end - start) * 1000)  # Convert to milliseconds

    return response_times


class TestAppointmentListPerformance:
    """Test performance of appointment list endpoint (calendar view)."""

    @pytest.mark.parametrize(
        "performance_dataset",
        ["small", "medium", "large"],
        indirect=True,
    )
    async def test_calendar_view_performance(
        self,
        client: AsyncClient,
        performance_dataset: dict[str, Any],
    ):
        """
        Test GET /appointments with date range (calendar view).

        Simulates therapist viewing their weekly or monthly calendar.
        """
        dataset = performance_dataset
        workspace = dataset["workspace"]
        headers = get_auth_headers(workspace.id)

        # Test weekly calendar view (7 days)
        start_date = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_date = start_date + timedelta(days=7)

        url = (
            f"/api/v1/appointments?"
            f"start_date={start_date.isoformat().replace('+00:00', 'Z')}&"
            f"end_date={end_date.isoformat().replace('+00:00', 'Z')}"
        )

        response_times = await measure_endpoint_performance(client, "get", url, headers)

        stats = calculate_stats(response_times)
        print(format_stats(stats, f"Calendar View - {dataset['size']} dataset"))

        # Assert performance targets
        assert stats["p95"] < P95_TARGET_MS, (
            f"p95 ({stats['p95']:.2f}ms) exceeds target ({P95_TARGET_MS}ms) "
            f"for {dataset['size']} dataset"
        )
        assert stats["p99"] < P99_TARGET_MS, (
            f"p99 ({stats['p99']:.2f}ms) exceeds target ({P99_TARGET_MS}ms) "
            f"for {dataset['size']} dataset"
        )
        assert stats["mean"] < MEAN_TARGET_MS, (
            f"Mean ({stats['mean']:.2f}ms) exceeds target ({MEAN_TARGET_MS}ms) "
            f"for {dataset['size']} dataset"
        )

    @pytest.mark.parametrize(
        "performance_dataset",
        ["small", "medium", "large"],
        indirect=True,
    )
    async def test_client_timeline_performance(
        self,
        client: AsyncClient,
        performance_dataset: dict[str, Any],
    ):
        """
        Test GET /appointments filtered by client_id.

        Simulates viewing all appointments for a specific client.
        """
        dataset = performance_dataset
        workspace = dataset["workspace"]
        test_client = dataset["clients"][0]
        headers = get_auth_headers(workspace.id)

        url = f"/api/v1/appointments?client_id={test_client.id}"

        response_times = await measure_endpoint_performance(client, "get", url, headers)

        stats = calculate_stats(response_times)
        print(format_stats(stats, f"Client Timeline - {dataset['size']} dataset"))

        # Assert performance targets
        assert stats["p95"] < P95_TARGET_MS, (
            f"p95 ({stats['p95']:.2f}ms) exceeds target ({P95_TARGET_MS}ms) "
            f"for {dataset['size']} dataset"
        )
        assert stats["mean"] < MEAN_TARGET_MS, (
            f"Mean ({stats['mean']:.2f}ms) exceeds target ({MEAN_TARGET_MS}ms) "
            f"for {dataset['size']} dataset"
        )

    @pytest.mark.parametrize(
        "performance_dataset",
        ["small", "medium", "large"],
        indirect=True,
    )
    async def test_paginated_list_performance(
        self,
        client: AsyncClient,
        performance_dataset: dict[str, Any],
    ):
        """
        Test GET /appointments with pagination.

        Simulates browsing through appointment history.
        """
        dataset = performance_dataset
        workspace = dataset["workspace"]
        headers = get_auth_headers(workspace.id)

        url = "/api/v1/appointments?page=1&page_size=50"

        response_times = await measure_endpoint_performance(client, "get", url, headers)

        stats = calculate_stats(response_times)
        print(format_stats(stats, f"Paginated List - {dataset['size']} dataset"))

        # Assert performance targets
        assert stats["p95"] < P95_TARGET_MS, (
            f"p95 ({stats['p95']:.2f}ms) exceeds target ({P95_TARGET_MS}ms) "
            f"for {dataset['size']} dataset"
        )
        assert stats["mean"] < MEAN_TARGET_MS, (
            f"Mean ({stats['mean']:.2f}ms) exceeds target ({MEAN_TARGET_MS}ms) "
            f"for {dataset['size']} dataset"
        )


class TestConflictDetectionPerformance:
    """Test performance of conflict detection endpoint."""

    @pytest.mark.parametrize(
        "performance_dataset",
        ["small", "medium", "large"],
        indirect=True,
    )
    async def test_conflict_check_performance(
        self,
        client: AsyncClient,
        performance_dataset: dict[str, Any],
    ):
        """
        Test GET /appointments/conflicts endpoint.

        Simulates real-time conflict checking as therapist drags appointments
        in the calendar UI.
        """
        dataset = performance_dataset
        workspace = dataset["workspace"]
        headers = get_auth_headers(workspace.id)

        # Check for conflicts in a typical appointment slot
        check_time = datetime.now(UTC).replace(
            hour=14, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

        end_time = (check_time + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        url = (
            f"/api/v1/appointments/conflicts?"
            f"scheduled_start={check_time.isoformat().replace('+00:00', 'Z')}&"
            f"scheduled_end={end_time}"
        )

        response_times = await measure_endpoint_performance(client, "get", url, headers)

        stats = calculate_stats(response_times)
        print(format_stats(stats, f"Conflict Detection - {dataset['size']} dataset"))

        # Conflict detection is critical for real-time UX - stricter targets
        assert stats["p95"] < CONFLICT_P95_TARGET_MS, (
            f"p95 ({stats['p95']:.2f}ms) exceeds target ({CONFLICT_P95_TARGET_MS}ms) "
            f"for {dataset['size']} dataset. Conflict detection requires "
            "<100ms p95 for real-time UX."
        )
        assert stats["mean"] < CONFLICT_MEAN_TARGET_MS, (
            f"Mean ({stats['mean']:.2f}ms) exceeds "
            f"target ({CONFLICT_MEAN_TARGET_MS}ms) for {dataset['size']} dataset. "
            "Conflict detection requires <50ms mean for real-time UX."
        )


class TestAppointmentCreatePerformance:
    """Test performance of appointment creation endpoint."""

    @pytest.mark.parametrize(
        "performance_dataset",
        ["small", "medium", "large"],
        indirect=True,
    )
    async def test_create_appointment_performance(
        self,
        client: AsyncClient,
        performance_dataset: dict[str, Any],
        test_user_ws1: User,
        redis_client,
    ):
        """
        Test POST /appointments endpoint performance.

        Simulates creating new appointments with conflict detection.
        Note: Each iteration creates a new appointment at different times.
        """
        dataset = performance_dataset
        workspace = dataset["workspace"]
        test_client = dataset["clients"][0]
        csrf_token = await add_csrf_to_client(
            client, workspace.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response_times = []
        base_time = datetime.now(UTC).replace(
            hour=9, minute=0, second=0, microsecond=0
        ) + timedelta(days=60)

        for i in range(NUM_ITERATIONS):
            # Create appointments at different times to avoid conflicts
            scheduled_start = base_time + timedelta(hours=i * 2)
            scheduled_end = scheduled_start + timedelta(hours=1)

            payload = {
                "client_id": str(test_client.id),
                "scheduled_start": scheduled_start.isoformat(),
                "scheduled_end": scheduled_end.isoformat(),
                "location_type": "clinic",
                "location_details": f"Room {i % 5}",
                "notes": f"Performance test appointment {i}",
            }

            start = time.perf_counter()
            response = await client.post(
                "/api/v1/appointments", headers=headers, json=payload
            )
            end = time.perf_counter()

            assert response.status_code == 201, (
                f"Create failed: {response.status_code} - {response.text}"
            )

            response_times.append((end - start) * 1000)

        stats = calculate_stats(response_times)
        print(format_stats(stats, f"Create Appointment - {dataset['size']} dataset"))

        # Create operations can be slightly slower due to conflict checks + write
        # But should still be fast for good UX
        assert stats["p95"] < P95_TARGET_MS, (
            f"p95 ({stats['p95']:.2f}ms) exceeds target ({P95_TARGET_MS}ms) "
            f"for {dataset['size']} dataset"
        )
        assert stats["mean"] < MEAN_TARGET_MS, (
            f"Mean ({stats['mean']:.2f}ms) exceeds target ({MEAN_TARGET_MS}ms) "
            f"for {dataset['size']} dataset"
        )


class TestConcurrentRequestPerformance:
    """Test performance under concurrent load."""

    async def test_concurrent_calendar_requests(
        self,
        client: AsyncClient,
        large_dataset: dict[str, Any],
    ):
        """
        Test concurrent calendar view requests.

        Simulates multiple therapists or browser tabs accessing the calendar
        simultaneously.
        """
        workspace = large_dataset["workspace"]
        headers = get_auth_headers(workspace.id)

        start_date = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end_date = start_date + timedelta(days=7)

        url = (
            f"/api/v1/appointments?"
            f"start_date={start_date.isoformat().replace('+00:00', 'Z')}&"
            f"end_date={end_date.isoformat().replace('+00:00', 'Z')}"
        )

        # Simulate 10 concurrent requests
        num_concurrent = 10
        response_times = []

        for _ in range(10):  # 10 batches of concurrent requests
            tasks = []
            for _ in range(num_concurrent):

                async def make_request():
                    start = time.perf_counter()
                    response = await client.get(url, headers=headers)
                    end = time.perf_counter()
                    assert response.status_code == 200
                    return (end - start) * 1000

                tasks.append(make_request())

            batch_times = await asyncio.gather(*tasks)
            response_times.extend(batch_times)

        stats = calculate_stats(response_times)
        print(format_stats(stats, "Concurrent Calendar Requests (large dataset)"))

        # Under concurrent load, p95 can be slightly higher
        # but should still meet targets with proper indexing
        assert stats["p95"] < P95_TARGET_MS * 1.5, (
            f"p95 ({stats['p95']:.2f}ms) exceeds concurrent target "
            f"({P95_TARGET_MS * 1.5}ms) for large dataset"
        )
        assert stats["mean"] < MEAN_TARGET_MS * 1.5, (
            f"Mean ({stats['mean']:.2f}ms) exceeds concurrent target "
            f"({MEAN_TARGET_MS * 1.5}ms) for large dataset"
        )


class TestPerformanceSummary:
    """Generate performance summary report."""

    async def test_generate_performance_summary(
        self,
        client: AsyncClient,
        small_dataset: dict[str, Any],
        medium_dataset: dict[str, Any],
        large_dataset: dict[str, Any],
        redis_client,
    ):
        """
        Generate comprehensive performance summary across all datasets.

        This test provides a quick overview of system performance.
        """
        # Flush Redis to reset rate limits before running many requests
        await redis_client.flushdb()

        results = []

        for dataset, name in [
            (small_dataset, "Small (10 clients, 50 appts)"),
            (medium_dataset, "Medium (50 clients, 500 appts)"),
            (large_dataset, "Large (100 clients, 1000 appts)"),
        ]:
            # Flush Redis before each dataset to reset rate limits
            # (each dataset makes 50 requests, total would be 150 > 100 limit)
            await redis_client.flushdb()

            workspace = dataset["workspace"]
            headers = get_auth_headers(workspace.id)

            # Test calendar view
            start_date = datetime.now(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_date = start_date + timedelta(days=7)
            url = (
                f"/api/v1/appointments?"
                f"start_date={start_date.isoformat().replace('+00:00', 'Z')}&"
                f"end_date={end_date.isoformat().replace('+00:00', 'Z')}"
            )

            response_times = await measure_endpoint_performance(
                client, "get", url, headers, iterations=50
            )
            stats = calculate_stats(response_times)

            results.append(
                {
                    "dataset": name,
                    "endpoint": "Calendar View (7 days)",
                    "stats": stats,
                }
            )

        # Print summary
        print("\n" + "=" * 80)
        print("PERFORMANCE SUMMARY")
        print("=" * 80)
        for result in results:
            print(f"\n{result['dataset']} - {result['endpoint']}")
            print(format_stats(result["stats"], "Results"))

        print("\n" + "=" * 80)
        print("PERFORMANCE TARGETS:")
        print(f"  Mean: < {MEAN_TARGET_MS}ms")
        print(f"  p95:  < {P95_TARGET_MS}ms")
        print(f"  p99:  < {P99_TARGET_MS}ms")
        print("=" * 80 + "\n")

        # Verify all results meet targets
        for result in results:
            stats = result["stats"]
            dataset = result["dataset"]
            assert stats["p95"] < P95_TARGET_MS, (
                f"p95 ({stats['p95']:.2f}ms) exceeds target for {dataset}"
            )
            assert stats["mean"] < MEAN_TARGET_MS, (
                f"Mean ({stats['mean']:.2f}ms) exceeds target for {dataset}"
            )
