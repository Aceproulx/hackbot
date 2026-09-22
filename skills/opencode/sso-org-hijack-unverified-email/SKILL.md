---
name: sso-org-hijack-unverified-email
description: >
  Use this skill during authorized bug bounty / pentest recon whenever a target is a B2B/multi-tenant SaaS app that supports "custom SSO" (Okta, Auth0, generic SAML/OIDC) in addition to the usual "Login with Google/Facebook/Apple" buttons — especially if custom SSO is hidden/not shown by default. Covers the org-hijack account takeover: unlike Google/Facebook/Apple, self-serve SSO providers like Okta/Auth0 don't require the attacker to prove ownership of an email when creating a user, so an attacker can create an Okta/Auth0 identity for the victim's real email, invite that email to an attacker-controlled organization on the target app, log in via the attacker's fake SSO identity, and if the target treats "verified via any SSO" as equivalent to "owns this email", gain access to the victim's other organizations/data on the same platform. Trigger on requests to test SSO/SAML login, multi-tenant/organization-switching features, or "custom SSO" account linking — always only against in-scope targets and your own test accounts/organizations.
metadata:
  source: https://rikeshbaniya.medium.com/account-takeover-using-sso-logins-fa35f28a358b
---

# Account Takeover via Unverified Custom-SSO Email

From Rikesh Baniya. Targets multi-tenant B2B apps that support enterprise/custom SSO providers (Okta, Auth0, generic SAML/OIDC) alongside consumer social logins.

## The core insight

Consumer OAuth providers (Google, Facebook, Apple) all require proof of email ownership before they'll authenticate a user with that address — you can't just declare `victim@gmail.com` as your Google account's email. **Self-service enterprise IdPs like Okta and Auth0 have no such requirement**: an attacker can spin up their own free Okta/Auth0 tenant and create a user object with `email = victim@realcompany.com` with zero verification. If the target app treats "authenticated via any linked SSO provider with this email" as proof of identity/org-membership, that's the exploitable gap.

## Step 1: Find the custom SSO option

Many apps only show Google/Facebook/Apple by default on the login page, but also support a "custom SSO" / "Enterprise SSO" / "SAML SSO" login path that's only reachable directly (not linked from the main login page) or surfaced only for orgs that have enabled it. Check:
- Login page source/network requests for hidden SSO provider options.
- App documentation or admin settings for "SSO", "SAML", "Okta", "Auth0", "Enterprise login".
- A direct URL pattern like `/sso`, `/enterprise-login`, `/saml/login`.

## Step 2: Confirm no verification is required to create a matching identity

Set up (or use) your own free Okta or Auth0 developer tenant. Create a user in it with the email field set to an address you also control (your own second test account on the target app) — confirm the IdP lets you do this without sending any verification email. This is the precondition; if the IdP you're testing against does require verification, this vector doesn't apply.

## Step 3: Understand the target's org model

Map out how the target app structures organizations/tenants:
- An org (e.g. `VictimOrganization`) has members identified by email (`victim@gmail.com`, others).
- A separate org can independently configure its own custom SSO (e.g. link its own Okta instance) — the admin of that org creates users in their Okta and links them to their org.
- Users can potentially belong to / switch between multiple organizations on the same platform if the same email is a member of more than one.

## Step 4: Execute the hijack

1. Attacker creates a new organization on the target app (`AttackerOrganization`) — this is normally self-service and requires no special privilege.
2. Attacker invites the victim's real email (`victim@gmail.com`) as a member of `AttackerOrganization`. (Confirm whether the invite requires the victim to accept, or whether membership/linkage is created immediately — either can matter depending on the app's flow.)
3. Attacker sets up custom SSO (Okta/Auth0) for `AttackerOrganization`, and in their own Okta/Auth0 tenant creates a user with `email = victim@gmail.com`.
4. Attacker logs into the target app via this custom-SSO path, authenticating as `victim@gmail.com` — but the identity is entirely attacker-controlled since they own the Okta tenant.
5. **The critical check:** since `victim@gmail.com` is also a genuine member of `VictimOrganization`, does the target app let the attacker (now "logged in as" `victim@gmail.com`) switch to / access `VictimOrganization`? If organization access is keyed purely on email match rather than on a verified, IdP-specific immutable identifier, the attacker now has the victim's access to `VictimOrganization` — potentially all its data and functionality.

## Reporting checklist

- Show that account/org access is being granted based on email match across SSO providers without cross-provider identity verification.
- Full walkthrough: creating `AttackerOrganization`, inviting the victim email, linking a self-created Okta/Auth0 identity for that email, and the resulting cross-org access — using two of your own test accounts/orgs, never a real victim's data.
- Recommend remediation: never treat "authenticated via SSO provider X with email Y" as proof of ownership of email Y across organizational boundaries; require out-of-band email verification (magic link) before granting cross-org access based on email match, or key identity on a provider-specific verified/immutable claim instead of email — the same underlying lesson as the nOAuth mutable-claims research.
