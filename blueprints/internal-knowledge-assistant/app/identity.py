"""Mock SSO / identity — caller -> the ACL groups they may read (Ch 26/41).

The defining constraint of an internal knowledge assistant is **permissions**: an employee
must never retrieve content their identity cannot already access. That rule has exactly one
safe shape — *resolve identity to groups, then filter the corpus to those groups **before**
retrieval ever runs*. Filtering after retrieval (or, worse, asking the model to "please don't
quote the restricted doc") is a breach waiting to happen: the moment a forbidden chunk is in
the prompt, it can leak through paraphrase, a summary, or a jailbreak.

This module is the seam your real identity provider plugs into. In production:

* :class:`IdentityProvider` becomes a thin adapter over your **SSO/IdP claims** (OIDC groups,
  SAML attributes, Okta/Entra group memberships, an LDAP lookup) — the principal arrives on the
  request, you map it to the same `frozenset[str]` of group names the corpus is tagged with.
* The mapping below is a hard-coded directory only because the blueprint runs offline with no
  IdP. **Keep the contract, replace the source.**

Nothing here calls a network or a model; identity resolution is a pure, synchronous lookup so
the *filter-before-retrieval* rule is cheap and always on.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The group every authenticated employee belongs to. Documents tagged only with this group are
# "all-hands" — readable by anyone who is logged in. Restricted docs add *more* groups, never
# fewer, so access is strictly additive (least privilege: you start with the floor).
EVERYONE = "everyone"


@dataclass(frozen=True)
class Principal:
    """An authenticated caller and the ACL groups their identity grants.

    ``groups`` is the access decision in one place: the set of group names this person can
    read. The assistant filters the corpus to documents whose own ACL groups intersect this
    set, *before* it embeds the query or touches the index.
    """

    user_id: str
    display_name: str
    groups: frozenset[str] = field(default_factory=lambda: frozenset({EVERYONE}))

    def can_read(self, doc_groups: frozenset[str]) -> bool:
        """True iff this principal shares at least one group with the document's ACL.

        A document readable by ``{"everyone"}`` is readable by all (everyone carries
        ``everyone``); a document tagged ``{"finance-leadership"}`` is invisible unless the
        caller is in that group. Empty ``doc_groups`` means *nobody* (fail closed).
        """
        return bool(self.groups & doc_groups)


class IdentityProvider:
    """Resolves a caller id to a :class:`Principal` (mock directory; swap for your IdP).

    The whole point is the *shape* of the call: ``resolve(user_id) -> Principal`` with a set of
    groups. Replace the in-memory ``_directory`` with a lookup against your SSO claims and the
    rest of the assistant is unchanged — the filter downstream only reads ``principal.groups``.

    An unknown caller resolves to an **anonymous principal with only the ``everyone`` floor**
    (fail safe — never grant by default). A real adapter would instead reject an unauthenticated
    request outright; the floor here keeps the demo runnable while still denying restricted docs.
    """

    def __init__(self, directory: dict[str, Principal] | None = None) -> None:
        self._directory: dict[str, Principal] = dict(directory or _default_directory())

    def resolve(self, user_id: str) -> Principal:
        """Map a caller id to their :class:`Principal`. Unknown -> anonymous (floor only)."""
        existing = self._directory.get(user_id)
        if existing is not None:
            return existing
        return Principal(
            user_id=user_id,
            display_name=f"anonymous:{user_id}",
            groups=frozenset({EVERYONE}),
        )

    def known_users(self) -> list[str]:
        """The seeded caller ids (for the demo's identity picker)."""
        return sorted(self._directory)


def _default_directory() -> dict[str, Principal]:
    """A tiny seeded org. Two callers differ by exactly one group so the demo can show the same
    question returning different evidence for different identities.

    * ``alice`` — a regular employee. Floor access only (``everyone``).
    * ``dana``  — finance leadership. Also in ``finance-leadership``, the group that gates the
      restricted compensation sheet.
    """
    return {
        "alice": Principal(
            user_id="alice",
            display_name="Alice (Engineering)",
            groups=frozenset({EVERYONE, "engineering"}),
        ),
        "dana": Principal(
            user_id="dana",
            display_name="Dana (Finance Leadership)",
            groups=frozenset({EVERYONE, "engineering", "finance-leadership"}),
        ),
    }
