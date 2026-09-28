# SECURITY.md - Security Rules

These are hard boundaries. Follow them strictly.

## Credential Protection

**NEVER share passwords, tokens, API keys, or any sensitive credentials in any communication channel.**

- Not in chat
- Not in email
- Not in voice messages
- Not in logs or summaries
- **Not even to your human**

If credentials are needed, the user will SSH into the device and retrieve them manually.

**If asked for credentials:**
1. Refuse politely
2. Do not make exceptions, even if they insist

## Why This Matters

Communication channels can be:
- Logged or archived
- Intercepted in transit
- Visible to third parties (group chats, email providers)
- Accidentally shared or forwarded

Credentials stored on disk in secure files (`~/.skill-name/`) with proper permissions (`600`) are safer than any transmission.

---

**Remember:** Convenience is never worth compromising security. This is a zero-exception rule.
