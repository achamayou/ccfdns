# Efficient delegation for aDNS

This document extends the single-zone
[micro aDNS cluster DNS service](./micro_aDNS.md). It describes an optional
multi-zone design with a separate zone authority for each zone. It also
describes proof-bearing DNS answers.

Each zone authority is a private authoritative-only server for exactly one
zone. It never performs forwarding or recursion.

The base proposal intentionally uses one zone. A later deployment can support
independently administered zones or proof-bearing answers. For this purpose,
each zone authority commits its zone to a separate Merkle tree. It signs the
root of each committed zone version. One root signature then replaces DNSSEC
signatures on the zone's RRsets.

This proposal defines an application-specific extension. It is not DNSSEC. A
resolver that supports only standard DNSSEC validation does not understand this
extension. A native aDNS-aware client can authenticate the encrypted transport
and ignore proofs. A proof-aware client uses an aDNS-specific response profile.

## Zone commitment

Each zone authority represents its zone as an authenticated ordered map. Each
key contains the canonical owner name, class, and RR type. Each value contains
the canonical RRset and its original authoritative TTL. Separate authenticated
metadata lists the types at each existing name. This metadata also represents
empty non-terminals. Thus, a proof can distinguish NXDOMAIN from NODATA. A
verifier can also reconstruct the exact value that includes the hashed TTL.

The tree profile defines the canonical DNS encoding and ordering. It also
defines the hash algorithm and domain separation. Conceptually:

```text
rrset_leaf = H("adns-rrset-v1" || zone || owner || class || type || rrset)
name_leaf  = H("adns-name-v1"  || zone || owner || sorted_types)
node       = H("adns-node-v1"  || left_child || right_child)
```

The exact byte encoding must be deterministic and versioned. Display strings
are not suitable hash inputs. JSON object order is also not suitable.

Before commit, aDNS produces a root claim such as:

```text
ZoneRootClaim {
  profile: "adns-merkle-v1",
  zone: "example.internal.",
  generation: 42,
  root_hash: h'...',
  valid_from: 1786032000,
  valid_until: 1786032300
}
```

The claim does not contain a CCF transaction ID. The ID does not exist when the
application sets the claims digest. The zone-generation transaction commits the
digest of the deterministic `ZoneRootClaim` encoding as a CCF application
claim.

After global commit, aDNS adds the assigned transaction ID:

```text
ZoneRoot {
  claim: ZoneRootClaim,
  ccf_transaction_id: "12.345"
}
```

The zone key or aDNS service key signs the complete `ZoneRoot`. aDNS then
publishes the root and its CCF receipt. A verifier checks the receipt and the
CCF service endorsement. It reconstructs `ZoneRootClaim` and computes its
digest. This digest must equal the receipt's application-claims digest. The
root signature binds the transaction ID to the claim. The generation and
validity interval limit replay. A stateful client records the latest accepted
generation. It rejects an older generation.

Each zone has a separate tree and root statement. An authenticated service
catalog maps each zone name to its authoritative-only server, current root key,
and policy. One service identity can sign every root when one operator controls
all zones. For separate administrators, the catalog commits the key and
authorization for each zone. Cross-organization delegation needs an additional
protocol. Parent-to-child proof chains also need an additional protocol. This
extension does not define these protocols.

The catalog also authenticates zone selection. The client finds the unique
managed zone with the longest matching suffix. It accepts the response only if
the stated origin is that zone. It also checks that the root and verification
key are current. Some catalog profiles cannot prove longest-suffix selection.
Such profiles must prohibit overlapping origins. Without this rule, an
untrusted cache could substitute a valid ancestor-zone root.

Post-quantum object authentication needs a post-quantum or hybrid root key. The
catalog path that authorizes this key must also use post-quantum or hybrid
trust anchors. A classical-only CCF receipt remains useful audit evidence. It
does not give post-quantum authentication to a root signature. The multiple
service identities and typed attestations proposed in
[CCF Discussion 7971](https://github.com/microsoft/CCF/discussions/7971)
can authorize separate classical and ML-DSA root signatures during migration.

## Answer proofs

A proof-bearing response contains the normal DNS answer, zone root identifier,
and minimum Merkle proof. The client first compares the response question with
the original canonical `(QNAME, QTYPE, QCLASS)`. The two questions must be
equal. The client derives the proof names from the current question. These
names include the owner, closest encloser, next-closer name, and wildcard
candidate.

The DNS response code must match the proof category. Positive, NODATA, and
wildcard proofs require `NOERROR`. An NXDOMAIN proof requires `NXDOMAIN`. The
proof must cover every RRset that the client uses from the Answer, Authority,
or Additional section. This includes the SOA that sets the RFC 2308 negative
cache lifetime. The client ignores an unproved RRset. If the client needs that
RRset to answer the query, it rejects the response. It also checks that the
proof authenticates each canonical owner, class, type, TTL-bearing value, and
RDATA that it uses.

- **Positive answer.** The proof shows the requested RRset at the current
  `QNAME`.
- **CNAME answer.** The proof shows the CNAME RRset at the current `QNAME`. The
  target becomes the `QNAME` for the next link. The client repeats the catalog,
  root, and proof checks for that link. It does this because a target can enter
  another managed zone. A target can also leave all managed zones. In that
  case, object verification stops at the proved CNAME. The aDNS root does not
  prove an external terminal answer. The client rejects loops and limits the
  number of links.
- **NODATA.** The proof shows that the owner exists. An empty non-terminal also
  counts as an existing owner. The committed type set at `QNAME` excludes
  `QTYPE` and CNAME.
- **NXDOMAIN.** The proof shows that the derived closest encloser exists. This
  can be an empty non-terminal. It shows that the derived next-closer name is
  absent. It also shows that the closest encloser has no wildcard child.
- **Wildcard answer.** The proof shows that the derived closest encloser
  exists. It shows that the derived next-closer name is absent. It proves that
  the requested RRset or CNAME exists at `*.<closest-encloser>`. It also binds
  the synthesized response owner to the current `QNAME`.
- **Wildcard NODATA.** The proof shows that the derived closest encloser
  exists. It shows that the derived next-closer name is absent. It proves that
  `*.<closest-encloser>` exists. The wildcard type set excludes `QTYPE` and
  CNAME.
- **Multiple RRsets.** A Merkle multiproof sends each shared tree path once.

Negative and wildcard proofs need special rules. A plain unordered Merkle tree
is not sufficient. The authenticated map must support absence or adjacency
proofs. It must also encode wildcard and empty-non-terminal semantics without
ambiguity.

A proof-aware client performs these checks:

1. compare the response question with the original question and derive all
   initial proof names from that question;
2. verify through the authenticated catalog that the stated origin is the
   unique longest matching managed zone and that its root key is current;
3. verify the CCF receipt and service endorsement for `ccf_transaction_id`;
4. reconstruct `ZoneRootClaim` and compare its digest with the receipt's
   application-claims digest;
5. verify the root signature and validity interval;
6. verify that the response name belongs to the stated zone;
7. verify the inclusion, absence, or wildcard proof against the root hash; and
8. check that each served TTL is not greater than the committed original TTL.
   Then limit positive and RFC 2308 negative caching to the remaining root
   validity. For each CNAME link, repeat these checks with the target as the new
   question name.

The client verifies the post-quantum signature when it first receives a root.
It then caches the verified root statement. Later answers for that zone usually
contain only hash paths. Thus, one large signature and public key protect many
answers for that zone version.

A proof-aware DoH client can request a versioned binary media type. This media
type contains the DNS message, root reference, and proof. The client can also
get the proof from a companion endpoint. DoT and DoQ need a negotiated EDNS
option or a parallel framed control message. These encodings are non-standard.
Thus, this mechanism is an optional extension to the single-zone design.

## Why the tree is friendlier to post-quantum signatures

DNSSEC adds at least one signature to each authoritative RRset. A response also
contains the signatures needed to validate its RRsets. Thus, a post-quantum
DNSSEC profile repeats its larger signatures for multiple RRsets.

With a Merkle-authenticated zone:

- one post-quantum signature authenticates a committed zone version;
- an update changes a logarithmic number of hashes;
- each committed batch needs one new root signature, not one signature for
  each affected RRset;
- positive and negative proofs contain fixed-size hashes instead of more
  public-key signatures; and
- a cached root signature validates many answers and Merkle multiproofs.

This design moves signature work from each RRset to each zone version. Most
proof work becomes hash operations. Proofs still have costs. A proof grows
logarithmically with the number of leaves. Frequent zone updates create new
roots. Clients also need more verification code. The system can batch related
Kubernetes updates. It can retain roots for a bounded overlap period. It can
also use multiproofs. These methods keep the costs predictable.

The extension also adds object security that the base design does not provide.
A verifier can check a proof-bearing answer outside its original connection.
The verifier must have a fresh, authenticated root. This permits untrusted
caches for proof-aware clients in the defined aDNS trust domain. It does not
replace DNSSEC on the public DNS.

## References

- [micro aDNS: a single-zone cluster DNS service for Kubernetes](./micro_aDNS.md)
- [RFC 2308: Negative Caching of DNS Queries](https://www.rfc-editor.org/rfc/rfc2308.html)
- [RFC 4033: DNS Security Introduction and
  Requirements](https://www.rfc-editor.org/rfc/rfc4033.html)
- [RFC 4034: Resource Records for the DNS Security
  Extensions](https://www.rfc-editor.org/rfc/rfc4034.html)
- [RFC 4035: Protocol Modifications for the DNS Security
  Extensions](https://www.rfc-editor.org/rfc/rfc4035.html)
- [CCF post-quantum identity proposal](https://github.com/microsoft/CCF/discussions/7971)
- [NIST FIPS 204: Module-Lattice-Based Digital Signature
  Standard](https://csrc.nist.gov/pubs/fips/204/final)
