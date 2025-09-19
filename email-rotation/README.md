# email-rotation

This directory implements an oncall rotation for security issues, essentially.

The intent of the code here is to help ensure that newly-reported security
issues are addressed promptly. When a new LLVM Security repo issue is filed,
a bot will send an email to the LLVM security group mailing list highlighting
the folks who are currently oncall, and who are expected to help push forward
on said issue.

## Rotation quick answers

### How long is a rotation?

2 weeks.

### How do I swap with someone?

Edit the `rotation.yaml` file to swap your github username with the person
you'd like to swap with. The machine this runs on checks for updates daily.

### How do I add myself to future rotations?

Add a line to `rotation-members.yaml` with your github username.

### How do I remove myself from future rotations?

1. Remove your username from `rotation-members.yaml`.
2. Edit `rotation.yaml` to remove _all_ rotations including and after your next
   rotation. (If your next rotation is not yet scheduled, you're done after
   step #1 is committed).
3. Run `./extend_rotation.py --ensure-weeks=16` and commit the result. (If your
   next rotation is more than two months out, this is optional).

### How is the emailing run?

@gburgessiv runs it via cron every few hours. Ideally, it would run on
something shared like Github Actions, but all GHA logs are public. Accidental
disclosure through that is a concerning vector, and it's very low-effort to
run locally.

### How is the rotation determined?

`./extend_rotation.py` is run ~monthly. It adds new rotations based on who in
`rotation-members.yaml` participated in the rotation least recently.

## Short descriptions of files

Relevant files (ignoring tests) are:

- `rotation-members.yaml`, which is the set of all members currently on the
  security group who are eligible for this rotation.

- `rotation.yaml`, which specifies the rotation. This is generally extended by
  `rotation-members.yaml`, though can be edited by humans (e.g., to remove
  people from rotations, swap with others, etc.)

- `email_about_issues.py` actually emails about the issues; it's run on
  a machine through a Docker image produced by the `Dockerfile`.
  The `docker run` invocation looks like:
  ```
  docker run --rm -it -v $PWD:/home/email-bot/llvm-security-repo llvm-security-group-emails
  ```
- `extend_rotation.py` extends the `rotation.yaml` file automatically. This
  script only appends to the rotation, and takes into account who's already been
  in the rotation recently when creating new rotation instances.
