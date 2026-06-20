# Archiving & Reposting CC-BY-NC Discord Assets: Legal & Practical Analysis

*Not legal advice. For a project whose explicit goal is to make content permanent against deletion, the data-protection layer is the one worth paying a UK data-protection specialist to review.*

The single most useful reframing: your plan touches **three separate legal regimes**, and they don't rise or fall together. You're on strong ground in one, on contractual thin ice in the second, and exposed in the third. Most of the "discrepancies" you noticed dissolve once you see they're being judged under different regimes.

---

## Layer 1 — Copyright / CC-BY-NC: your "no backsies" is basically right

The irrevocability you're relying on is real. CC licenses say so in their own text: the licensor cannot revoke these freedoms as long as you follow the license terms. A creator who deletes their Discord post hasn't revoked anything — CC licenses are not revocable; once a work is published under a CC license, licensees may continue using it for the duration of copyright protection, even though the licensor may stop distributing it.

- Creative Commons license deed / text: <https://creativecommons.org/licenses/by-nc/4.0/>
- Wikimedia Commons, *License revocation*: <https://commons.wikimedia.org/wiki/Commons:License_revocation>
- Naval War College, *Creative Commons* guide: <https://usnwc.libguides.com/copyright/creativecommons>

So reposting a deleted asset, with attribution and the NC restriction intact, is fine **as a copyright matter**.

Two caveats that actually matter:

**Validity of the auto-license depends on the poster owning the work.** Only a rightsholder can apply a CC license. Your rule auto-licenses "all original work," but if someone posts an asset they don't own, or that embeds third-party IP (a borrowed texture, a model, a font, someone else's mesh), the auto-license is void as to that portion and reposting it infringes the real owner. Your "free public content only" rule reduces this but doesn't eliminate it — keep a takedown/DMCA path regardless. Discord's Developer Terms also require DMCA compliance for third-party content in your app (§7b).

**CC only ever covers copyright.** Per Creative Commons themselves: CC licenses do not license rights other than copyright and similar rights; they do not license the publicity, personality, and privacy rights of third parties.

- Creative Commons FAQ: <https://creativecommons.org/faq/>

In 4.0 the licensor *does* waive their *own* privacy/personality rights to the limited extent needed to exercise the license — if you license a photograph of yourself, you may not later assert a privacy right to have it removed. That actually helps you against an author who later wants their own asset pulled on privacy grounds. But that waiver is a private-law matter between two parties. It does not touch statutory data-protection rights, and it does nothing about third parties whose data might be in an asset. That's Layer 3.

---

## Layer 2 — Discord Developer Terms & Policy: the contractual exposure

Here's where staying private and small does real, load-bearing work, and where the public-site element creates the most tension.

**Why "small" matters: you dodge App Review entirely.** Reading message content needs the Message Content privileged intent. The rule: this affects only verified bots in 100 or more servers; unverified bots are not affected at all. Under 100 servers you just toggle it on in the portal — no justification, no review. Your "us plus a few friend servers" plan sits comfortably below that, so you never have to defend the use case.

- Message Content Intent FAQ: <https://support-dev.discord.com/hc/en-us/articles/4404772028055>
- Practical 2026 intents guide: <https://space-node.net/blog/discord-gateway-intents-message-content-2026>

**But if you ever did apply, the use case is the kind Discord rejects.** Their review philosophy is explicit that "just resurfacing the message content you're collecting in a new way generally isn't considered transformative," and they look for features that are unique, compelling, and/or transformative, non-invasive, and that put user privacy and safety front and center. "Archive and repost" is close to the textbook example of non-transformative resurfacing. So scaling past the friend-server stretch is a hard wall, not a gradient.

- Message Content Intent Review Policy: <https://support-dev.discord.com/hc/en-us/articles/5324827539479-Message-Content-Intent-Review-Policy>

**Provisions that bite even at your size** (the Developer Terms apply to everyone regardless of server count):

- **§5(b) third-party sharing.** You may not share API Data with third parties except with a Service Provider, where legally required, or where the user directs it. A public static site arguably *is* disclosure of API Data to the entire world. This is the single biggest ToS friction with your design — and the thing that distinguishes you from ordinary logging bots.
- **§5(b) deletion on request.** The terms require you to promptly delete API Data when the applicable user (or Discord) requests it, and to give users an easily accessible way to ask for their API Data to be modified and deleted. This directly conflicts with "no backsies / kept forever." Under the *contract*, a user can demand deletion even though the *CC license* is irrevocable — because this clause is about API Data, not copyright.
- **§5(a) privacy policy.** You must maintain a publicly-linked, GDPR-compliant privacy policy describing what you collect, how you use/share it, and how to request deletion. Mandatory, not optional.
- **Developer Policy #20 — no scraping.** "Do not mine or scrape any data, content, or information available on or through Discord services." Using the documented gateway/API event flow for its intended purpose isn't "scraping" in the ordinary sense, but bulk-harvesting full channel history to build an external corpus sits close enough to the line that it's a judgment call. Archive only your specific forum channels, only the content you need, via the documented flow.
- **Developer Policy #21 — no AI training** on message content without Discord's permission. Relevant if the archive ever feeds a model.

- Developer Terms of Service (full text): <https://support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service>
- Developer Policy: <https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy>

---

## Layer 3 — UK GDPR: the statutory layer the license can't override

This is where "explain the discrepancies" really lands, and it's the layer your design most under-weights.

**The "we're just a small community" defense fails the moment you publish.** GDPR has a personal/household exemption, but the CJEU's *Lindqvist* ruling (C-101/01) is directly on point: the exemption covers only activities carried out in the course of private or family life, which is clearly not the case with processing consisting in publication on the internet so that the data are made accessible to an indefinite number of people. *Ryneš* (C-212/13) reinforces this. A public static site = indefinite audience = you are a data controller, full UK GDPR applies.

- Household exemption explainer (quoting Lindqvist): <https://www.cookieyes.com/knowledge-base/gdpr/does-gdpr-apply-to-individuals/>
- ICO, guide to exemptions (domestic purposes): <https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/exemptions/a-guide-to-the-data-protection-exemptions/>

**What's personal data here?** The assets themselves usually aren't, but the *attribution* is — usernames, user IDs, avatars, the credit line that CC-BY actually *requires* you to display. So the very thing the license obligates you to publish is regulated personal data.

**The CC license does not extinguish GDPR rights.** This is the core of the conflict. As the Oral History Society puts it, for personal data offered under a CC licence the only legal basis that would suffice is the consent of the data subject, which can be withdrawn at any time. Copyright irrevocability and data-protection irrevocability are different things; a CC license is irrevocable *as to copyright* and silent *as to data protection*.

- Oral History Society, GDPR guidance: <https://ohs.org.uk/gdpr-2/>

**The right to erasure is real but not absolute — and your best defenses are narrower than they look.** Article 17(3) carves out, among others, freedom of expression/information and archiving in the public interest / scientific or historical research where erasure would render the processing impossible or seriously impair it. The freedom-of-expression angle is plausible for a community archive; the "public interest archiving" angle is more of a stretch — it has a fairly specific meaning, and the ICO is clear you should not apply the exemptions in a blanket fashion, only as necessary and proportionate, case by case. You'd most likely run on "legitimate interests" (preservation + discoverability) with a documented balancing test, not consent (withdrawable consent defeats the point).

- ICO, right to erasure: <https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/individual-rights/right-to-erasure/>
- Art. 17 GDPR: <https://gdpr-info.eu/art-17-gdpr/>
- National Archives, archiving personal data FAQ: <https://www.nationalarchives.gov.uk/archives-sector/legislation/archives-data-protection-law-uk/gdpr-faqs/>

**The Git element is the sharpest practical problem.** Article 17(2) says where you've made data public and are obliged to erase it, you must take reasonable steps, including technical measures, to inform other controllers processing it. Git history is append-only by design; downloadable archives and mirrors propagate copies you can't recall. Your preservation mechanism and the erasure obligation are in direct architectural tension. Don't bake usernames into immutable commit metadata — keep attribution in a mutable sidecar so you can scrub a credit without rewriting the whole asset history.

---

## The three discrepancies you flagged, explained

**MEE6 / Carl / Dyno full message logging.** The resolution is that *logging ≠ publishing*. These bots write content to a private mod channel inside the same server, or to their own DB, for the server's own moderation — the data stays within Discord's trust boundary and is visible only to staff. They also respond to deletion requests and run on a "necessary for stated functionality" basis: MEE6's own GDPR response shows database storage limited to user ID, username, discriminator and avatar, encrypted, with access removed when you de-authorize or leave. Their tolerance is also conditional and shrinking — the August 2022 message-content crackdown was Discord deliberately tightening exactly this category. "Big bots do it" is survivorship, not safe harbor. Your plan crosses the line they mostly respect: external public republication, persisting past deletion.

- MEE6 GDPR response: <https://gist.github.com/Catbuttes/cb6c2cffafdf573e405613c3afcb6532>

**Discord not deleting message content on account deletion.** Discord anonymizes — deleted accounts are renamed to "Deleted User#0000," the profile image is removed, and the user leaves all servers — but the message text stays, on a "preserve conversation flow" rationale that's widely criticized because anonymization leaves text intact and re-identification remains practicable. Two reasons this doesn't transfer to you. First, Discord is the *first-party platform controller* with its own balancing tests and the argument that messages are part of conversations others co-authored; you inherit none of that and add public external permanence. Second — the cautionary part — Discord's own retention practice was found *unlawful*: CNIL fined Discord €800,000 in November 2022 for, among other things, failing to define and respect a data retention period, after finding ~2.47 million French accounts inactive for over three years still retained. So Discord isn't a model of "keep it forever, it's fine" — it's an example of a company penalized for keeping data too long.

- Discord forum thread on deletion behavior: <https://support.discord.com/hc/en-us/community/posts/360052389053>
- Analysis of anonymization vs. erasure: <https://factually.co/fact-checks/technology/delete-discord-account-remove-dms-server-messages-before-anonymization-3334c0>
- CNIL fines Discord €800,000: <https://www.cnil.fr/en/discord-inc-fined-800-000-euros>

**Answer Overflow reposting to an external website.** This is your closest precedent and the most useful, because it's tolerated *precisely because of how it was engineered* — the opposite of "no backsies." AO's founder noted Discord's privacy policy doesn't let you publicly share users' messages without them consenting first, so the project built a lot around driving user consent. Their default is **not public**: a non-consenting user's messages are shown only to visitors who are in the same server; public display requires the user to consent via a slash command or server-level consent, obtainable through "read the rules" membership screening. So AO treats public display as **opt-in and reversible**. Your "automatic, irreversible" model is the inverse. The lesson isn't "AO proves you can repost" — it's "AO shows the mechanism that makes reposting defensible," and that mechanism is consent-gating plus honored opt-out.

- AO founder on consent (Hacker News): <https://news.ycombinator.com/item?id=32387645>
- AO docs, displaying messages: <https://docs.answeroverflow.com/user-settings/displaying-messages>

---

## What I'd actually change to de-risk it

The throughline: keep the copyright "no backsies" (valid), but stop letting it stand in for data-protection permanence (not valid). Concretely:

1. **Separate the *work* from the *personal data*.** You can keep asserting the irrevocable CC license over the asset while still honoring an erasure/opt-out request for the attribution. If an author wants out, you can keep the asset but strip or anonymize the credit, or take it down — what you can't honestly promise is "we will never remove it."
2. **Build a real, evidenced consent gate.** Put the licensing + archiving + external-publication + Git-permanence terms into membership screening / rules acceptance, AO-style, so you can show each user agreed. A rule nobody provably accepted is weak both as a CC license grant and as a GDPR lawful basis / transparency matter.
3. **Ship the mandatory pieces:** a public privacy policy linked in the Developer Portal (Developer Terms §5a), an easy deletion/opt-out path (§5b), and the announcement you're already planning.
4. **Decide your Git-erasure procedure before launch** (mutable attribution sidecar, not username-in-commit).
5. **Don't train AI on the corpus** without separate permission (Policy §21).
6. **Keep a DMCA/takedown route** for third-party-IP and third-party-personal-data problems.
7. **Stay under 100 servers** — but treat that as avoiding scrutiny, not earning approval.

---

### Source index

- Discord Developer Terms of Service: <https://support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service>
- Discord Developer Policy: <https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy>
- Message Content Intent Review Policy: <https://support-dev.discord.com/hc/en-us/articles/5324827539479-Message-Content-Intent-Review-Policy>
- Message Content Privileged Intent FAQ: <https://support-dev.discord.com/hc/en-us/articles/4404772028055>
- Discord Privacy Policy: <https://discord.com/privacy>
- Creative Commons FAQ: <https://creativecommons.org/faq/>
- CC BY-NC 4.0: <https://creativecommons.org/licenses/by-nc/4.0/>
- Wikimedia Commons, License revocation: <https://commons.wikimedia.org/wiki/Commons:License_revocation>
- ICO, right to erasure: <https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/individual-rights/right-to-erasure/>
- ICO, guide to exemptions: <https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/exemptions/a-guide-to-the-data-protection-exemptions/>
- Art. 17 GDPR: <https://gdpr-info.eu/art-17-gdpr/>
- Oral History Society, GDPR: <https://ohs.org.uk/gdpr-2/>
- CNIL fines Discord €800,000: <https://www.cnil.fr/en/discord-inc-fined-800-000-euros>
- Answer Overflow docs: <https://docs.answeroverflow.com/user-settings/displaying-messages>
- MEE6 GDPR response: <https://gist.github.com/Catbuttes/cb6c2cffafdf573e405613c3afcb6532>
