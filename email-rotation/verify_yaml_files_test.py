#!/usr/bin/env python3

import unittest

import rotations


class TestRotationYamlFilesParse(unittest.TestCase):
    """Ensures our yaml files parse."""

    def test_rotation_members_yaml_parses(self) -> None:
        parsed = rotations.RotationMembersFile.parse_file(
            rotations.ROTATION_MEMBERS_FILE
        )
        self.assertTrue(parsed.members, "No rotation members could be parsed")

    def test_rotation_yaml_parses(self) -> None:
        parsed = rotations.RotationFile.parse_file(rotations.ROTATION_FILE)
        self.assertTrue(parsed.rotations, "No rotations could be parsed")


if __name__ == "__main__":
    unittest.main()
