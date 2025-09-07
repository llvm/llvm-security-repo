This directory implements an oncall rotation for security issues, essentially.

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
