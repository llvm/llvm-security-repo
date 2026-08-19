#!/usr/bin/env python3

import datetime
import unittest
from unittest import mock

import email_about_issues as email
import rotations

# Test constant for email configuration
TEST_EMAIL_INFO = email.ScriptEmailInfo(
    creds=email.EmailCreds(
        username="test_user@example.com",
        password="fake_password123",
    ),
    recipient="foo@bar.com",
)


class TestEmailAboutIssues(unittest.TestCase):
    @mock.patch.object(rotations.RotationMembersFile, "parse_file")
    @mock.patch.object(rotations.RotationFile, "parse_file")
    def test_load_rotation_state_returns_expected(
        self, mock_rotationfile_parse: mock.Mock, mock_membersfile_parse: mock.Mock
    ) -> None:
        mock_membersfile_parse.return_value = rotations.RotationMembersFile(
            members=["alice", "bob", "carol"]
        )

        mock_rotationfile_parse.return_value = rotations.RotationFile(
            rotations=[
                rotations.Rotation(
                    start_time=datetime.datetime.fromtimestamp(1000.0),
                    members=["alice"],
                ),
                rotations.Rotation(
                    start_time=datetime.datetime.fromtimestamp(1500.0),
                    members=["bob"],
                ),
                rotations.Rotation(
                    start_time=datetime.datetime.fromtimestamp(1800.0),
                    members=["carol"],
                ),
            ]
        )

        result = email.load_rotation_state(1600)
        assert result  # use `assert` so pyright doesn't complain below
        self.assertEqual(result.current_members, {"bob"})
        self.assertEqual(result.all_members, {"alice", "bob", "carol"})
        self.assertEqual(result.final_rotation_start, 1800.0)

    @mock.patch.object(email, "try_email_llvm_security_team")
    def test_maybe_email_about_rotation_end_sends_email(
        self, mock_send_email: mock.Mock
    ) -> None:
        invocation = email.ScriptInvocation(
            repo_name="repo",
            github_token="token",
            now_timestamp=2000.0,
            email_info=TEST_EMAIL_INFO,
        )
        state = email.ScriptState(seen_advisories=[], last_alert_about_rotation=None)
        rotation_state = email.RotationState(
            all_members={"a", "b"},
            current_members={"a"},
            final_rotation_start=2000.0
            - email.SECONDS_BEFORE_ROTATION_LIST_END_TO_NAG
            + 1,
        )
        mock_send_email.return_value = True
        new_state = email.maybe_email_about_rotation_end(
            invocation, state, rotation_state
        )
        mock_send_email.assert_called_once()
        self.assertNotEqual(new_state, state)
        self.assertEqual(new_state.last_alert_about_rotation, invocation.now_timestamp)

    @mock.patch.object(email, "try_email_llvm_security_team")
    def test_maybe_email_about_rotation_end_no_email_if_too_early(
        self, mock_send_email: mock.Mock
    ) -> None:
        invocation = email.ScriptInvocation(
            repo_name="repo",
            github_token="token",
            now_timestamp=2000.0,
            email_info=TEST_EMAIL_INFO,
        )
        state = email.ScriptState(seen_advisories=[], last_alert_about_rotation=None)
        rotation_state = email.RotationState(
            all_members={"a", "b"},
            current_members={"a"},
            final_rotation_start=invocation.now_timestamp
            + email.SECONDS_BEFORE_ROTATION_LIST_END_TO_NAG
            + 1,
        )
        mock_send_email.return_value = True
        new_state = email.maybe_email_about_rotation_end(
            invocation, state, rotation_state
        )
        mock_send_email.assert_not_called()
        self.assertEqual(new_state, state)

    @mock.patch.object(email, "try_email_llvm_security_team")
    def test_maybe_email_about_rotation_end_respects_alert_interval(
        self, mock_send_email: mock.Mock
    ) -> None:
        invocation = email.ScriptInvocation(
            repo_name="repo",
            github_token="token",
            now_timestamp=2000.0,
            email_info=TEST_EMAIL_INFO,
        )
        state = email.ScriptState(
            seen_advisories=[], last_alert_about_rotation=invocation.now_timestamp
        )
        rotation_state = email.RotationState(
            all_members={"a", "b"},
            current_members={"a"},
            final_rotation_start=2000.0 - email.SECONDS_BEFORE_ROTATION_LIST_END_TO_NAG,
        )
        mock_send_email.return_value = True
        new_state = email.maybe_email_about_rotation_end(
            invocation, state, rotation_state
        )
        mock_send_email.assert_not_called()
        self.assertEqual(new_state, state)

    def test_scriptstate_json_roundtrip(self) -> None:
        original = email.ScriptState(
            seen_advisories=["a", "b"], last_alert_about_rotation=123.45
        )
        as_json = original.to_json()
        reconstructed = email.ScriptState.from_json(as_json)
        self.assertEqual(original, reconstructed)

    @mock.patch.object(email, "fetch_all_security_advisories_of_type")
    def test_list_unpublished_security_advisories_handles_none_collaborators(
        self, mock_fetch: mock.Mock
    ) -> None:
        mock_fetch.side_effect = [
            [
                {
                    "ghsa_id": "GHSA-1111-2222-3333",
                    "summary": "Advisory",
                    "state": "draft",
                    "collaborating_users": None,
                },
            ],
            [],
        ]

        advisories = email.list_unpublished_security_advisories("repo", "token")
        self.assertEqual(
            advisories,
            [
                email.SecurityAdvisory(
                    id="GHSA-1111-2222-3333",
                    title="Advisory",
                    collaborators=[],
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
