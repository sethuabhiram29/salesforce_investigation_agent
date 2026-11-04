---
id: LOGIN-10
domain: Login
version: 1
title: User Email Address Not Verified in Salesforce
description: Salesforce User account email address is unverified, preventing Single Sign-On and portal authentication.
tags:
  - login
  - email-verification
  - ciam
  - portal
  - authentication
---

# Context & Symptoms
Users report an authentication error or inability to log in to Salesforce or the Partner/Customer Community portal. Salesforce requires all email addresses to be verified before authentication assertions succeed. When an account is created or the email address is changed, an unverified email status blocks SSO assertions and direct portal logins until the verification link is clicked.

### Diagnostic Indicators:
- User exists in NA Org and `IsActive = True`.
- `User.EmailVerified = False` in Salesforce User record.
- Caller states "email not verified", "verification email expired", or gets authentication challenge regarding unverified email.

---

# Safety Rules

### Preconditions:
1. User record must exist in the Salesforce organization.
2. `User.IsActive` must be `True`.
3. `User.EmailVerified` must be `False` (or email verification is pending).

### Prohibited Actions:
- Do NOT modify the user's `Email` or `FederationIdentifier` directly without identity team approval.
- Do NOT deactivate or freeze the user account.
- Do NOT mark the incident as resolved until verification instructions are communicated and delivery is confirmed.

### Rollback Plan:
- If guidance or verification email was triggered for the wrong account, document the correction in ServiceNow work notes and notify the user.

---

# Resolution Steps

1. Retrieve incident and caller details from ServiceNow ticket.
2. Search user in NA Org using Salesforce SOSL/SOQL search.
3. If user not found in NA Org, follow Login-1A/Login-1B cross-org process.
4. Verify user operational status: confirm `User.IsActive = True`.
5. Retrieve user email attributes: inspect `User.Email` and `User.EmailVerified`.
6. Validate that `User.EmailVerified = False` or verification status is pending.
7. Trigger resend of Salesforce email verification link to user's registered corporate email address (`User.Email`).
8. If automated resend API is unavailable, document step-by-step guidance for the user and administrator:
   - Provide direct instructions for the user to check spam/junk folders for the Salesforce verification email.
   - Instruct administrator on how to trigger "Resend Verification Email" from the Salesforce User detail page in Setup.
9. Update ServiceNow incident work notes detailing:
   - Account email verification status (`EmailVerified: False`).
   - Registered email address where verification was dispatched.
   - Instructions provided to the user.
10. Inform user of action taken and resolve incident once user confirms verification completion.

---

# Required Remediation Fields

- **Target Object:** `User`
- **Target Field:** `Guidance`
- **Action Type:** `COMMUNICATION_GUIDANCE`
- **Proposed Value:** `Salesforce User email address is unverified, blocking portal and SSO login. Dispatch email verification link to user's corporate email and provide verification completion instructions.`

---

# Communication Template

```text
Hello {caller_name},

Our investigation into your Salesforce login issue indicates that your registered corporate email address ({user_email}) has not yet been verified in Salesforce, which is preventing authentication.

Actions Taken:
1. Confirmed your Salesforce account is active.
2. Verified that an email verification link is required to activate portal/SSO access.
3. Dispatched / requested a fresh verification email link to: {user_email}.

Next Steps:
- Please check your email inbox (including spam/junk folders) for an email from Salesforce with the subject "Verify your Salesforce email address".
- Click the verification link inside the email to complete the verification process.
- Once verified, attempt logging in again at https://bdx.my.salesforce.com.

If you do not receive the verification email within 15 minutes, please reply to this ticket.
```

---

# State Verification Checks

- **Pre-Remediation:** `User.IsActive == True AND User.EmailVerified == False`
- **Post-Remediation:** Guidance delivered to ServiceNow work notes, and user instructed to complete email verification.
