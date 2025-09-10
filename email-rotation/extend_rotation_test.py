#!/usr/bin/env python3

import datetime
import unittest
from unittest.mock import patch

from extend_rotation import (
    MIN_TIME_UTC,
    calculate_rotations_to_cover,
    find_most_recent_service_times,
    generate_additional_rotations,
)
from rotations import Rotation

MOCKED_NOW_UTC = datetime.datetime(2025, 5, 30, 10, 0, 0, tzinfo=datetime.timezone.utc)
EXPECTED_FIRST_ROTATION_START_NO_PRIORS = datetime.datetime(
    2025, 5, 25, 0, 0, 0, tzinfo=datetime.timezone.utc
)


class TestFindMostRecentServiceTimes(unittest.TestCase):
    def test_no_rotations(self) -> None:
        members = ["alice", "bob"]
        result = find_most_recent_service_times([], members)
        expected = {
            "alice": MIN_TIME_UTC,
            "bob": MIN_TIME_UTC,
        }
        self.assertEqual(result, expected)

    def test_basic_rotations(self) -> None:
        members = ["alice", "bob", "charlie"]
        time1 = datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc)
        time2 = datetime.datetime(2023, 1, 15, tzinfo=datetime.timezone.utc)

        prior_rotations = [
            Rotation(start_time=time1, members=["alice", "bob"]),
            Rotation(start_time=time2, members=["charlie", "alice"]),
        ]
        result = find_most_recent_service_times(prior_rotations, members)
        expected = {
            "alice": time2,
            "bob": time1,
            "charlie": time2,
        }
        self.assertEqual(result, expected)

    def test_member_in_multiple_rotations_gets_latest(self) -> None:
        members = ["alice", "bob", "charlie"]
        time1 = datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc)
        time2 = datetime.datetime(2023, 1, 15, tzinfo=datetime.timezone.utc)
        time3 = datetime.datetime(2023, 2, 1, tzinfo=datetime.timezone.utc)
        prior_rotations = [
            Rotation(start_time=time1, members=["alice", "bob"]),
            Rotation(start_time=time2, members=["charlie", "alice"]),
            Rotation(start_time=time3, members=["bob"]),
        ]
        result = find_most_recent_service_times(prior_rotations, members)
        expected = {
            "alice": time2,
            "bob": time3,
            "charlie": time2,
        }
        self.assertEqual(result, expected)


class TestCalculateRotationsToCover(unittest.TestCase):
    def test_no_existing_rotations_raises_error(self) -> None:
        when = datetime.datetime(2025, 6, 1, tzinfo=datetime.timezone.utc)
        with self.assertRaises(ValueError):
            calculate_rotations_to_cover(
                when, rotation_length_weeks=2, current_rotations=[]
            )

    def test_target_time_before_last_rotation_end_returns_zero(self) -> None:
        last_rotation_start = datetime.datetime(
            2025, 5, 1, tzinfo=datetime.timezone.utc
        )
        first_rotation_start = last_rotation_start - datetime.timedelta(weeks=2)
        current_rotations = [
            Rotation(start_time=first_rotation_start, members=["bob", "charlie"]),
            Rotation(start_time=last_rotation_start, members=["alice", "bob"]),
        ]

        # Target time is May 10th, which is before the rotation ends on the
        # 15th.
        when = datetime.datetime(2025, 5, 10, tzinfo=datetime.timezone.utc)
        result = calculate_rotations_to_cover(
            when, rotation_length_weeks=2, current_rotations=current_rotations
        )
        self.assertEqual(result, 0)

    def test_one_rotation_needed(self) -> None:
        # Last rotation starts May 1st, with 2-week length it ends May 15th
        last_rotation_start = datetime.datetime(
            2025, 5, 1, tzinfo=datetime.timezone.utc
        )
        current_rotations = [
            Rotation(start_time=last_rotation_start, members=["alice", "bob"])
        ]

        # Target time is May 20th, needs one more 2-week rotation, since the
        # previous one ends on the 15th.
        when = datetime.datetime(2025, 5, 20, tzinfo=datetime.timezone.utc)
        result = calculate_rotations_to_cover(
            when, rotation_length_weeks=2, current_rotations=current_rotations
        )
        self.assertEqual(result, 1)

    def test_multiple_rotations_needed(self) -> None:
        last_rotation_start = datetime.datetime(
            2025, 5, 1, tzinfo=datetime.timezone.utc
        )
        current_rotations = [
            Rotation(start_time=last_rotation_start, members=["alice", "bob"])
        ]

        # Target time is June 10th, needs multiple rotations. May 15 to June 10
        # is about 26 days, which is about 3.7 weeks. With 2-week rotations, we
        # need 2 rotations (4 weeks total).
        when = datetime.datetime(2025, 6, 10, tzinfo=datetime.timezone.utc)
        result = calculate_rotations_to_cover(
            when, rotation_length_weeks=2, current_rotations=current_rotations
        )
        self.assertEqual(result, 2)


class TestGenerateAdditionalRotations(unittest.TestCase):
    def test_generate_no_prior_rotations(self) -> None:
        members = ["alice", "bob", "charlie"]
        rotation_length_weeks = 1
        people_per_rotation = 2

        # The function returns an Iterator[Rotation]
        generator = generate_additional_rotations(
            [], members, rotation_length_weeks, people_per_rotation, now=MOCKED_NOW_UTC
        )
        generated_list = [next(generator) for _ in range(2)]

        expected_start_time1 = EXPECTED_FIRST_ROTATION_START_NO_PRIORS
        self.assertEqual(generated_list[0].start_time, expected_start_time1)
        self.assertEqual(generated_list[0].members, ["alice", "bob"])

        expected_start_time2 = expected_start_time1 + datetime.timedelta(weeks=1)
        self.assertEqual(generated_list[1].start_time, expected_start_time2)
        self.assertEqual(generated_list[1].members, ["charlie", "alice"])

    def test_generate_with_prior_rotations(self) -> None:
        prior_time = datetime.datetime(
            2025, 5, 5, 0, 0, 0, tzinfo=datetime.timezone.utc
        )
        prior_rotations = [
            Rotation(start_time=prior_time, members=["memberA", "memberB"])
        ]
        members = ["memberC", "memberA", "memberB"]

        rotation_length_weeks = 2
        people_per_rotation = 1

        generator = generate_additional_rotations(
            prior_rotations,
            members,
            rotation_length_weeks,
            people_per_rotation,
            now=MOCKED_NOW_UTC,
        )
        generated_list = [next(generator) for _ in range(3)]

        expected_start1 = prior_time + datetime.timedelta(weeks=2)
        self.assertEqual(generated_list[0].start_time, expected_start1)
        self.assertEqual(generated_list[0].members, ["memberC"])

        expected_start2 = expected_start1 + datetime.timedelta(weeks=2)
        self.assertEqual(generated_list[1].start_time, expected_start2)
        self.assertEqual(generated_list[1].members, ["memberA"])

        expected_start3 = expected_start2 + datetime.timedelta(weeks=2)
        self.assertEqual(generated_list[2].start_time, expected_start3)
        self.assertEqual(generated_list[2].members, ["memberB"])


if __name__ == "__main__":
    unittest.main()
