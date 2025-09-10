#!/usr/bin/env python3

import argparse
import collections
import dataclasses
import datetime
import itertools
import logging
import math
from pathlib import Path
from typing import Iterator

import rotations

MIN_TIME_UTC = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)


def find_most_recent_service_times(
    rotations: list[rotations.Rotation],
    members: list[str],
) -> dict[str, datetime.datetime]:
    """Returns a dictionary mapping member names to their last service date."""
    # Give new people the minimum possible service time, so they're
    # scheduled promptly.
    last_service_times = {x: MIN_TIME_UTC for x in members}
    for rotation in rotations:
        service_time = rotation.start_time
        for member in rotation.members:
            # `rotations` is always in the order of oldest to newest, so we can
            # just overwrite old values here.
            last_service_times[member] = service_time

    return last_service_times


def generate_additional_rotations(
    prior_rotations: list[rotations.Rotation],
    members: list[str],
    rotation_length_weeks: int,
    people_per_rotation: int,
    now: datetime.datetime,
) -> Iterator[rotations.Rotation]:
    """Generates new rotations based on the given parameters."""
    # Super simple algorithm: the least recent person to serve on the rotation
    # gets added first. If there's a tie, randomly choose between them.
    #
    # In the face of swaps, this will not necessarily be completely fair, but
    # rotations are very infrequent anyway. If it's a problem, we can figure out
    # something better.
    last_service_times = find_most_recent_service_times(prior_rotations, members)
    least_recent_assignees = collections.deque(
        name
        for name, _ in sorted(
            last_service_times.items(),
            key=lambda item: item[1],
        )
    )

    rotation_length = datetime.timedelta(weeks=rotation_length_weeks)
    if prior_rotations:
        next_rotation_start_time = prior_rotations[-1].start_time + rotation_length
    else:
        # Choose the most recent Sunday, at midnight UTC, as the start time for the first rotation.
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        next_rotation_start_time = midnight - datetime.timedelta(
            days=midnight.weekday() + 1
        )

    while True:
        people_on_this_rotation = []
        for _ in range(people_per_rotation):
            people_on_this_rotation.append(least_recent_assignees.popleft())

        yield rotations.Rotation(
            start_time=next_rotation_start_time,
            members=people_on_this_rotation,
        )
        next_rotation_start_time += rotation_length
        least_recent_assignees.extend(people_on_this_rotation)


def calculate_rotations_to_cover(
    when: datetime.datetime,
    rotation_length_weeks: int,
    current_rotations: list[rotations.Rotation],
) -> int:
    """Calculates how many additional rotations are needed to cover up to `when`."""
    if not current_rotations:
        raise ValueError("No existing rotations to extend from.")

    last_rotation = current_rotations[-1]
    rotation_length = datetime.timedelta(weeks=rotation_length_weeks)
    end_of_last_rotation = last_rotation.start_time + rotation_length

    if end_of_last_rotation >= when:
        return 0

    delta = when - end_of_last_rotation
    # Use total seconds to account for any non-day components of `delta`.
    days_needed = math.ceil(delta.total_seconds() / (24 * 60 * 60))
    weeks_needed = days_needed / 7
    rotations_needed = int(math.ceil(weeks_needed / rotation_length_weeks))
    return rotations_needed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extend a rotation with additional members."
    )
    parser.add_argument(
        "--rotation-file",
        type=Path,
        default=rotations.ROTATION_FILE,
        help="Path to the rotation YAML file.",
    )
    parser.add_argument(
        "--rotation-members-file",
        type=Path,
        default=rotations.ROTATION_MEMBERS_FILE,
        help="Path to the rotation members YAML file.",
    )
    parser.add_argument(
        "--rotation-length-weeks",
        type=int,
        default=2,
        help="Length of each rotation in weeks. Default is %(default)d.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="""
        If set, this script will print the new rotation file to stdout, rather
        than overwriting the existing file.
        """,
    )
    parser.add_argument(
        "--people-per-rotation",
        type=int,
        default=2,
        help="Number of people per rotation. Default is %(default)d.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )

    rotation_group = parser.add_mutually_exclusive_group()
    rotation_group.add_argument(
        "--num-rotations",
        type=int,
        help="Number of rotations to add, defaults to 5.",
    )
    rotation_group.add_argument(
        "--ensure-weeks",
        type=int,
        help="""
        Ensure the rotation schedule covers at least this many weeks into
        the future.
        """,
    )
    return parser.parse_args()


def main() -> None:
    opts = parse_args()

    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: %(message)s",
        level=logging.DEBUG if opts.debug else logging.INFO,
    )

    dry_run: bool = opts.dry_run
    people_per_rotation: int = opts.people_per_rotation
    rotation_file_path: Path = opts.rotation_file
    rotation_length_weeks: int = opts.rotation_length_weeks
    rotation_members_file_path: Path = opts.rotation_members_file

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    members_file = rotations.RotationMembersFile.parse_file(rotation_members_file_path)
    current_rotation = rotations.RotationFile.parse_file(rotation_file_path)

    # Determine number of rotations based on flags
    if opts.num_rotations is not None:
        num_rotations_to_add: int = opts.num_rotations
    elif opts.ensure_weeks is not None:
        ensure_weeks: int = opts.ensure_weeks
        num_rotations_to_add = calculate_rotations_to_cover(
            now + datetime.timedelta(weeks=ensure_weeks),
            rotation_length_weeks,
            current_rotation.rotations,
        )
        if num_rotations_to_add == 0:
            logging.info(
                "Current rotations already cover the next %d weeks; no new rotations needed.",
                ensure_weeks,
            )
            return
        logging.info(
            "Ensuring %d weeks of coverage with %d rotations (%d weeks per rotation)",
            ensure_weeks,
            num_rotations_to_add,
            rotation_length_weeks,
        )
    else:
        # Default to 5 rotations if neither flag is specified
        num_rotations_to_add = 5

    rotation_generator = generate_additional_rotations(
        current_rotation.rotations,
        members_file.members,
        people_per_rotation,
        rotation_length_weeks,
        now=now,
    )

    extra_rotations = list(itertools.islice(rotation_generator, num_rotations_to_add))
    new_rotations = current_rotation.rotations + extra_rotations
    new_rotations_file = dataclasses.replace(current_rotation, rotations=new_rotations)

    if dry_run:
        logging.info("Dry-run mode enabled. Not writing to file; would've written:")
        print(new_rotations_file.to_yaml_str())
        return

    logging.info("Writing new rotations to file: %s", rotation_file_path)
    # On UNIX, ensure atomic writes. In any case, if to_yaml_str() raises, this
    # won't wipe out the old file.
    tmp_rotation_file_path = rotation_file_path.with_suffix(".tmp")
    with tmp_rotation_file_path.open("w") as f:
        f.write(new_rotations_file.to_yaml_str())
    tmp_rotation_file_path.rename(rotation_file_path)
    logging.info("New rotations written successfully.")


if __name__ == "__main__":
    main()
