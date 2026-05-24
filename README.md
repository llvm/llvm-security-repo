This repository exists to enable reporting of LLVM security issues to the [LLVM
security group](https://llvm.org/docs/Security.html) using GitHub's "privately
reporting a security vulnerability" workflow, see
<https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability>.

Unfortunately, due to the volume of reports we've received that have not
met community standards, we are requiring the addition of two footers to each
security report:

- `I-have-reviewed-SECURITY-md`: this is a self-certification that you have
  read and understood our [SECURITY.md](SECURITY.md) (and, more importantly,
  the LLVM `SECURITY.md` linked from it). Many LLVM binaries do **not** consider
  most bugs, including crashes, to be security vulnerabilities.
- `I-used-an-LLM-in-generating-this-report`: this is a self-certification about
  whether an LLM was a significant contributor to your report. If this is
  `yes`, it is **also** a self-certification that you have read and understood
  the [LLVM AI Tool Use Policy](https://llvm.org/docs/AIToolPolicy.html). If
  this is `no`, you are certifying that LLMs were not a significant contributor
  to the report, and you needn't read the policy.

These should be placed at the bottom of your report, and formatted like so:

```
I-have-reviewed-SECURITY-md: yes
I-used-an-LLM-in-generating-this-report: yes
```

These are not machine parsed; feel free to add commentary beyond yes|no if you
feel it's appropriate. Please keep the names consistent though - they're meant
to be easy to ctrl+f for.

**If your report lacks these**, we are likely to ask you to add them before we
read your report.
