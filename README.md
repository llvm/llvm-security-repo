This repository exists to enable reporting of LLVM security issues to the [LLVM
security group](https://llvm.org/docs/Security.html) using GitHub's "privately
reporting a security vulnerability" workflow, see
<https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability>.

Please follow these guidelines when submitting a report:

- Open separate security advisories for separate reports. Do not group multiple
  unrelated issues into a single report.
- Due to the volume of reports we've received that have not met community
  standards, we require the addition of two footers at the end of every
  security report:

  - `I-have-reviewed-SECURITY-md`: This is a self-certification that you have
    read and understood [LLVM's `SECURITY.md`](https://github.com/llvm/llvm-project/blob/main/SECURITY.md)
    and the [LLVM security documentation on what is a security
    issue](https://llvm.org/docs/Security.html#what-is-considered-a-security-issue).
    Notably, many LLVM binaries do **not** consider most bugs, including
    crashes, memory corruption, etc, to be security vulnerabilities.
  - `I-used-AI-in-this-report`: This is a self-certification about whether AI
    or tool-generated content was a significant contributor to your report. If
    this is `yes`, you **must** read and comply with the [LLVM AI Tool Use
    Policy](https://llvm.org/docs/AIToolPolicy.html), and you must clearly state
    how the tool-generated content was used (for example, by listing the tools
    used and the extent of their contribution). If this is `no`, you are
    certifying that AI/tool-generated content was not a significant contributor
    to the report.

These should be placed at the bottom of your report, and formatted like so:

```
I-have-reviewed-SECURITY-md: yes
I-used-AI-in-this-report: no
```

Or, if you used AI:

```
I-have-reviewed-SECURITY-md: yes
I-used-AI-in-this-report: yes; Claude originally flagged the bug, I validated it and wrote this disclosure.
```

If in doubt whether your AI use is significant, tend toward yes.

**If your report lacks these**, we will ask you to add them before we read your
report.
