#!/usr/bin/env python3

"""
Emails the LLVM Security Team about any new draft security advisories,
mentioning folks who are oncall.
"""

import argparse
import dataclasses
import datetime
import json
import logging
import os
import smtplib
import textwrap
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import requests

import rotations

GhsaId = str

# How many seconds before the end of _all_ scheduled rotations to wait before
# emailing folks to extend the rotation list.
SECONDS_BEFORE_ROTATION_LIST_END_TO_NAG = 14 * 24 * 60 * 60
SECONDS_BETWEEN_ROTATION_REFRESH_EMAILS = 24 * 60 * 60


@dataclasses.dataclass(frozen=True)
class EmailCreds:
    username: str
    password: str


@dataclasses.dataclass(frozen=True, eq=True)
class ScriptState:
    # Advisories seen on the last run of this script, so we don't send duplicate emails.
    seen_advisories: list[GhsaId]
    # If the rotation end is coming near, this tracks the last time we alerted about it.
    # Don't want to alert more than once per day.
    last_alert_about_rotation: float | None = None

    @classmethod
    def from_json(cls, json_data: dict[str, Any]) -> "ScriptState":
        return cls(
            seen_advisories=json_data.get("seen_advisories", []),
            last_alert_about_rotation=json_data.get("last_alert_about_rotation"),
        )

    def to_json(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def load_from_file(cls, state_file: Path) -> "ScriptState":
        try:
            with state_file.open(encoding="utf-8") as f:
                return cls.from_json(json.load(f))
        except FileNotFoundError:
            return cls(seen_advisories=[])

    def save_to_file(self, state_file: Path) -> None:
        tmp_file = state_file.with_suffix(".tmp")
        with tmp_file.open("w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, indent=2, ensure_ascii=False)
        tmp_file.rename(state_file)


@dataclasses.dataclass(frozen=True)
class ScriptEmailInfo:
    creds: EmailCreds
    recipient: str


# Flags passed to the script,
@dataclasses.dataclass(frozen=True)
class ScriptInvocation:
    repo_name: str
    github_token: str
    now_timestamp: float
    email_info: ScriptEmailInfo | None


@dataclasses.dataclass(frozen=True)
class SecurityAdvisory:
    id: GhsaId
    title: str
    collaborators: list[str]


def extract_next_page_from_header(resp: requests.Response) -> str | None:
    """Extracts the next page URL from the Link header of the response."""
    link_header = resp.headers.get("Link")
    if not link_header:
        return None

    for link in link_header.split(","):
        split_link = link.split(";", 1)
        if len(split_link) < 2:
            logging.warning("Malformed Link: %s", link)
            continue
        url, meta = split_link
        if 'rel="next"' in meta:
            return url.strip("<> ")
    return None


def requests_get_with_retry(url: str, headers: dict[str, Any]) -> requests.Response:
    i = 0
    max_retries = 3
    while True:
        resp = requests.get(url, headers=headers)
        if resp.ok:
            return resp
        logging.warning("GETing %s failed: %d %s", url, resp.status_code, resp.text)
        if i >= max_retries:
            resp.raise_for_status()
        i += 1
        time.sleep(i * 60)


def fetch_all_security_advisories_of_type(
    repo_name: str,
    github_token: str,
    state: str,
) -> list[dict[str, Any]]:
    """Iterates all security advisories for the given repo."""
    # Uses the API here:
    # https://docs.github.com/en/rest/security-advisories/repository-advisories?apiVersion=2022-11-28#list-repository-security-advisories
    url: str | None = (
        f"https://api.github.com/repos/{repo_name}/security-advisories?state={state}"
    )
    request_headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "GitHub-Api-Version": "2022-11-28",
    }
    results = []
    while url:
        resp = requests_get_with_retry(
            url,
            headers=request_headers,
        )

        results += resp.json()
        url = extract_next_page_from_header(resp)

    return results


def list_unpublished_security_advisories(
    repo_name: str, github_token: str
) -> list[SecurityAdvisory]:
    results = []
    total_security_advisories = 0
    advisories = fetch_all_security_advisories_of_type(repo_name, github_token, "draft")
    advisories += fetch_all_security_advisories_of_type(
        repo_name, github_token, "triage"
    )
    for advisory in advisories:
        logging.debug("Examining advisory %s", advisory)

        total_security_advisories += 1
        state = advisory["state"]
        # This should be guaranteed by the
        # 'fetch_all_security_advisories_of_type' function.
        assert state in ("draft", "triage"), state

        collaborators = [x["login"] for x in advisory.get("collaborating_users", ())]
        results.append(
            SecurityAdvisory(
                id=advisory["ghsa_id"],
                title=advisory["summary"],
                collaborators=collaborators,
            )
        )

    results.sort(key=lambda x: x.id)
    logging.info("Total security advisories fetched: %d", total_security_advisories)
    logging.info("%d draft security advisories found.", len(results))
    return results


@dataclasses.dataclass(frozen=True)
class RotationState:
    all_members: set[str]
    current_members: set[str]
    final_rotation_start: float


def load_rotation_state(now_timestamp: float) -> RotationState | None:
    rotation_members_file = rotations.RotationMembersFile.parse_file(
        rotations.ROTATION_MEMBERS_FILE,
    )
    rotation_file = rotations.RotationFile.parse_file(
        rotations.ROTATION_FILE,
    )

    current_rotation = None
    # Pick the most recent rotation with a timstamp <= now
    for rotation in rotation_file.rotations:
        if rotation.start_time.timestamp() > now_timestamp:
            break
        current_rotation = rotation

    if not current_rotation:
        return None

    return RotationState(
        all_members=set(rotation_members_file.members),
        current_members=set(current_rotation.members),
        final_rotation_start=rotation_file.rotations[-1].start_time.timestamp(),
    )


def try_email_llvm_security_team(
    email_creds: EmailCreds,
    email_recipient: str,
    subject: str,
    body: str,
) -> bool:
    """Returns True if the email was sent successfully."""
    try:
        # Create a multipart message
        message = MIMEMultipart()
        message["From"] = email_creds.username
        message["To"] = email_recipient
        message["Subject"] = subject
        # Add body to email
        message.attach(MIMEText(body, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()

            server.login(email_creds.username, email_creds.password)

            server.sendmail(email_creds.username, email_recipient, message.as_string())

        logging.info("Email sent successfully to %s", email_recipient)
        return True
    except Exception as e:
        logging.exception("Failed to send email with subject '%s'", subject)
        return False


def email_about_advisory(
    email_creds: EmailCreds,
    email_recipient: str,
    repo_name: str,
    advisory: SecurityAdvisory,
    oncall_members: list[str],
) -> bool:
    """Sends an email; returns True if successful."""
    return try_email_llvm_security_team(
        email_creds=email_creds,
        email_recipient=email_recipient,
        subject=f"New security advisory for {repo_name}: {advisory.title}",
        body=textwrap.dedent(
            f"""\
            A new security advisory has been created for {repo_name}.

            Please take action within two days. The security group members
            currently on the rotation are: {', '.join(oncall_members)}.

            Advisory URL: https://github.com/{repo_name}/security/advisories/{advisory.id}
            """
        ),
    )


def maybe_email_about_rotation_end(
    invocation: ScriptInvocation,
    state: ScriptState,
    rotation_state: RotationState | None,
) -> ScriptState:
    if rotation_state:
        time_to_last_start = (
            rotation_state.final_rotation_start - invocation.now_timestamp
        )
        if time_to_last_start > SECONDS_BEFORE_ROTATION_LIST_END_TO_NAG:
            logging.info(
                "Not emailing about rotation end: %d seconds left.",
                time_to_last_start,
            )
            return state

    if state.last_alert_about_rotation:
        time_since_last_alert = (
            invocation.now_timestamp - state.last_alert_about_rotation
        )
        if time_since_last_alert < SECONDS_BETWEEN_ROTATION_REFRESH_EMAILS:
            logging.info(
                "Not emailing about rotation end: already alerted within the last %d seconds.",
                SECONDS_BETWEEN_ROTATION_REFRESH_EMAILS,
            )
            return state

    new_state = dataclasses.replace(
        state,
        last_alert_about_rotation=invocation.now_timestamp,
    )

    email_info = invocation.email_info
    if not email_info:
        logging.info(
            "dry-run: would send email about rotation end for %s",
            invocation.repo_name,
        )
        return new_state

    if rotation_state:
        pretty_last_rotation_start = time.strftime(
            "%Y-%m-%d %H:%M:%S %Z",
            time.localtime(rotation_state.final_rotation_start),
        )
        issue = f"the last rotation starts at {pretty_last_rotation_start}"
    else:
        issue = "no rotation is currently scheduled"

    email_ok = try_email_llvm_security_team(
        email_creds=email_info.creds,
        email_recipient=email_info.recipient,
        subject=f"Rotation schedule running short for {invocation.repo_name}",
        body=textwrap.dedent(
            f"""\
            The rotation schedule is running short; {issue}.

            Please extend it by running `./extend_rotation.py` in the
            {invocation.repo_name} repo and committing the results.

            This nag email will be sent daily until the rotation is extended.

            Thank you!
            """
        ),
    )
    if not email_ok:
        return state

    return new_state


def run_script(
    invocation: ScriptInvocation,
    script_state: ScriptState,
    rotation_state: RotationState,
) -> ScriptState:
    draft_security_advisories = list_unpublished_security_advisories(
        invocation.repo_name,
        invocation.github_token,
    )

    failed_alerts_for_advisories = set()
    current_oncall = sorted(rotation_state.current_members)
    for advisory in draft_security_advisories:
        has_rotation_member = any(
            member in rotation_state.current_members
            for member in advisory.collaborators
        )

        if advisory.id in script_state.seen_advisories:
            logging.info(
                "Skipping advisory %s: already seen/alerted.",
                advisory.id,
            )
            continue

        if has_rotation_member:
            logging.info(
                "Skipping advisory %s: already has rotation member(s) as collaborator.",
                advisory.id,
            )
            continue

        email_info = invocation.email_info
        if not email_info:
            logging.info(
                "dry-run: would send email about advisory %s, mentioning %s",
                advisory.id,
                current_oncall,
            )
            continue

        email_success = email_about_advisory(
            email_creds=email_info.creds,
            email_recipient=email_info.recipient,
            repo_name=invocation.repo_name,
            advisory=advisory,
            oncall_members=current_oncall,
        )

        if not email_success:
            failed_alerts_for_advisories.add(advisory.id)

    return dataclasses.replace(
        script_state,
        seen_advisories=sorted(
            x.id
            # You can't unpublish advisories, so no need to keep ones
            # exclusively in the old state around.
            for x in draft_security_advisories
            # Pretend we didn't see advisories we failed to alert about, so we
            # try again next time.
            if x.id not in failed_alerts_for_advisories
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Respond to new issues in a GitHub repository."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually modify issues.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        required=True,
        help="State file used for tracking issues we've seen.",
    )
    parser.add_argument(
        "--github-repo",
        default=os.getenv("GITHUB_REPOSITORY"),
        help="GitHub repository in the format 'owner/repo'. Defaults to GITHUB_REPOSITORY env var.",
    )
    parser.add_argument(
        "--github-token",
        default=os.getenv("GITHUB_TOKEN"),
        help="GitHub API token. Defaults to GITHUB_TOKEN env var.",
    )
    parser.add_argument(
        "--email-username",
        default=os.getenv("GMAIL_USERNAME"),
        help="Email (Gmail) username. Defaults to GMAIL_USER env var.",
    )
    parser.add_argument(
        "--email-password",
        default=os.getenv("GMAIL_PASSWORD"),
        help="Email (Gmail) password. Defaults to GMAIL_PASSWORD env var.",
    )
    parser.add_argument(
        "--email-recipient",
        default=os.getenv("EMAIL_RECIPIENT"),
        help="Recipient email address. Defaults to EMAIL_RECIPIENT env var.",
    )

    args = parser.parse_args()

    if not args.github_repo:
        parser.error(
            "GitHub repository must be specified either via --github-repo or GITHUB_REPOSITORY env var."
        )
    if not args.github_token:
        parser.error(
            "GitHub token must be specified either via --github-token or GITHUB_TOKEN env var."
        )

    if not args.dry_run:
        if not args.email_username:
            parser.error(
                "Email username must be specified either via --email-username or GMAIL_USER env var."
            )
        if not args.email_password:
            parser.error(
                "Email password must be specified either via --email-password or GMAIL_PASSWORD env var."
            )
        if not args.email_recipient:
            parser.error(
                "Recipient email must be specified either via --email-recipient or EMAIL_RECIPIENT env var."
            )

    return args


def main() -> None:
    opts = parse_args()

    logging.basicConfig(
        format=">> %(asctime)s: %(levelname)s: %(filename)s:%(lineno)d: %(message)s",
        level=logging.DEBUG if opts.debug else logging.INFO,
    )

    now = time.time()
    state_file: Path = opts.state_file
    dry_run: bool = opts.dry_run
    email_info = None
    if not dry_run:
        email_info = ScriptEmailInfo(
            creds=EmailCreds(
                username=opts.email_username, password=opts.email_password
            ),
            recipient=opts.email_recipient,
        )

    script_state = ScriptState.load_from_file(state_file)
    rotation_state = load_rotation_state(now)
    script_invocation = ScriptInvocation(
        repo_name=opts.github_repo,
        github_token=opts.github_token,
        now_timestamp=now,
        email_info=email_info,
    )

    if rotation_state:
        new_script_state = run_script(
            invocation=script_invocation,
            script_state=script_state,
            rotation_state=rotation_state,
        )
    else:
        new_script_state = script_state
        logging.warning(
            "No rotation state found; not sending any emails about security advisories."
        )

    if rotation_state:
        new_script_state = maybe_email_about_rotation_end(
            invocation=script_invocation,
            state=new_script_state,
            rotation_state=rotation_state,
        )

    if new_script_state == script_state:
        return

    if dry_run:
        write_to_file = state_file.with_suffix(".dry-run")
        logging.info("dry-run: writing new state to file %s", write_to_file)
    else:
        logging.debug("Writing new state file...")
        write_to_file = state_file
    new_script_state.save_to_file(write_to_file)


if __name__ == "__main__":
    main()
