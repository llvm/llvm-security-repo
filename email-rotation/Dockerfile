FROM debian:stable-slim
LABEL maintainer="George Burgess <george.burgess.iv@gmail.com>"

# Grab the packages
RUN apt-get update
RUN apt-get install -y python3 python3-requests python3-yaml

ENV LANG=C.UTF-8

# Rootn't
RUN \
  useradd email-bot && \
  mkdir /home/email-bot && \
  chown email-bot:email-bot /home/email-bot

USER email-bot
WORKDIR /home/email-bot

# Example build'n'run invocation:
# docker build -t llvm-security-group-emails . && docker run --rm -it -v $PWD:/home/email-bot/llvm-security-repo/email-rotation llvm-security-group-emails
#
# Example `secrets` file:
# export EMAIL_RECIPIENT=receiver@redacted.com
# export GITHUB_REPOSITORY=llvm/llvm-security-repo
# export GITHUB_TOKEN=[redacted]
# export GMAIL_PASSWORD=[redacted]
# export GMAIL_USERNAME=sender@redacted.com
CMD ["bash", "-c", "cd llvm-security-repo && . secrets && exec ./email_about_issues.py --state-file=state.json --debug"]
