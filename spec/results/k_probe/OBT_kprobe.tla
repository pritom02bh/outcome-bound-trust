-------------------------------- MODULE OBT --------------------------------
(* Outcome-Bound Trust, v0.2 (FIXES F6).

   The round runs the eight DESIGN §5 phases in order:
     env -> verify -> budget -> remediate -> messages -> propose -> gate -> execute
   Nondeterminism appears only where the real system has it: deliveries and
   invoice prices (env), what suppliers claim (messages), and what the buyer
   proposes (propose). The verifier outcome follows from the modeled receipts.

   Modeled: the full §6 gate table (NO_CITATION, UNKNOWN_CLAIM,
   WRONG_COUNTERPARTY, BAD_CLAIM, CLAIM_MISMATCH incl. minimum lead time,
   PRICE_MISMATCH, OVER_CLAIM, OVERPAY, OVER_BUDGET), capacity consumed
   earliest-deadline first, exposure = consumed x claimed price (price level 1),
   B(c) with the cool-down, P(c) over orders, receipt allocation (F3, δ = 0),
   LAPSED, gated capped payments with inflated invoices (PRICE claims fail),
   phase-4 shortfall remediation + flags, phase-8 reroute of blocked orders.

   Invariants (identical wording in CLAUDE.md and DESIGN §7):
     I1 Gate safety: every action that becomes EXECUTED passes the full §6
        table at that moment; P(c) <= B(c) after every execution.
     I2 Earned trust: B(c) rises only in a verifier step that sets a claim of c
        to PASSED.
     I3 Ledger integrity: only PENDING -> PASSED | FAILED | LAPSED (LAPSED only
        if consumed = 0), only by the verifier; terminal statuses never change.
     I4 Propagation: a FAILED claim's citing actions and notes are flagged in
        the same step.
     I6 Capacity: for every DELIVERY claim, consumed <= qty.
     I7 Receipt uniqueness: every received unit is credited to at most one claim,
        and only to a claim of the supplier and item that delivered it.
   (I5, context isolation, is a unit test.)

   MUTANT removes one enforcing guard: "I1" budget row, "I2" cool-down floor,
   "I4" same-step flagging, "I6" capacity (OVER_CLAIM + capped consumption),
   "I7" receipt bookkeeping in allocation, "ITEM" the same-item binding (every
   cited claim, DELIVERY or PRICE, must be for the order's item, else
   CLAIM_MISMATCH; caught as an I1 violation, since I1 re-checks the full
   table). Two cross-supplier mutants: "XSUP-RECEIPT" allocation ignores the
   supplier (units of one supplier credited to another's claim; I7), and
   "XSUP-BUDGET" a PASSED claim earns budget for every supplier (I2).
   "none" is the real system.

   Symmetry: the claim, order and payment id pools are declared symmetry sets
   (Symm below). That is sound only if no step tells ids apart, so nothing here
   picks an id with CHOOSE unless the candidates are interchangeable: fresh
   claim ids are picked with \E (a fresh id may already be cited as an unknown
   claim), and earliest-deadline ties in consumption and allocation are broken
   nondeterministically. The code breaks those ties by claim_id, which is one
   of the modeled choices, so safety here implies safety of the code. All
   checked properties are safety properties (invariants and [][A]_vars). *)
EXTENDS Naturals, FiniteSets, TLC

CONSTANTS Sups, Items, Claims, Orders, Pays, Notes, MaxRound, B0, W, MinLead, MUTANT, K,
          NoRef      \* model value: the order a not-yet-proposed payment refers to

\* Symmetry needs every sentinel outside the permuted pools (ids are model values in the cfg).
ASSUME K \in Nat \ {0}
ASSUME NoRef \notin Claims \cup Orders \cup Pays

Phases == <<"env", "verify", "budget", "remediate", "messages", "propose", "gate", "execute">>
Idx(p) == CHOOSE i \in 1..8 : Phases[i] = p
NextPhase(p) == Phases[Idx(p) + 1]

Dead == {"FAILED", "UNTESTABLE", "LAPSED"}
Rounds == 1..MaxRound
RKeys == Rounds \X Sups \X Items

VARIABLES now, phase, cl, od, py, nt, rq, rc, made

vars == <<now, phase, cl, od, py, nt, rq, rc, made>>

NoClaim == [st |-> "NONE", sup |-> CHOOSE s \in Sups : TRUE, item |-> CHOOSE i \in Items : TRUE,
            tmpl |-> "-", qty |-> 0, by |-> 0, created |-> 0, consumed |-> 0, exposure |-> 0,
            resolved |-> 0, alloc |-> 0, remedied |-> FALSE]
NoOrder == [st |-> "NONE", sup |-> CHOOSE s \in Sups : TRUE, item |-> CHOOSE i \in Items : TRUE,
            qty |-> 0, cites |-> {}, round |-> 0, exec |-> FALSE, infl |-> FALSE,
            invoiced |-> FALSE, rerouted |-> FALSE]
NoPay == [st |-> "NONE", sup |-> CHOOSE s \in Sups : TRUE, ref |-> NoRef,
          amount |-> 0, cites |-> {}, exec |-> FALSE]

RECURSIVE SumQty(_), SumAmt(_), SumRem(_), SumAlloc(_), SumArr(_)
SumQty(S) == IF S = {} THEN 0 ELSE LET x == CHOOSE x \in S : TRUE IN od[x].qty + SumQty(S \ {x})
SumAmt(S) == IF S = {} THEN 0 ELSE LET x == CHOOSE x \in S : TRUE IN py[x].amount + SumAmt(S \ {x})
SumRem(S) == IF S = {} THEN 0 ELSE LET x == CHOOSE x \in S : TRUE IN cl[x].qty - cl[x].consumed + SumRem(S \ {x})
SumAlloc(S) == IF S = {} THEN 0 ELSE LET x == CHOOSE x \in S : TRUE IN cl[x].alloc + SumAlloc(S \ {x})
SumArr(S) == IF S = {} THEN 0 ELSE LET x == CHOOSE x \in S : TRUE IN rq[x] + SumArr(S \ {x})
MaxOf(S) == IF S = {} THEN 0 ELSE CHOOSE m \in S : \A y \in S : y <= m
Min2(a, b) == IF a < b THEN a ELSE b

----------------------------------------------------------------------------
(* Budget and pending exposure (DESIGN §6). *)
FailedOf(s) == {k \in Claims : cl[k].sup = s /\ cl[k].st = "FAILED"}
LastFail(s) == MaxOf({cl[k].resolved : k \in FailedOf(s)})
Bud(s) ==
    IF FailedOf(s) # {} /\ now - LastFail(s) < W THEN B0
    ELSE LET floor == IF FailedOf(s) = {} \/ MUTANT = "I2" THEN 0 ELSE LastFail(s) + W
             earned == {cl[k].exposure : k \in {j \in Claims : (cl[j].sup = s \/ MUTANT = "XSUP-BUDGET") /\ cl[j].tmpl = "D"
                                                  /\ cl[j].st = "PASSED" /\ cl[j].resolved >= floor}}
         IN B0 + K * MaxOf(earned)          \* K: budget growth multiplier (DECISIONS D36); K = 1 is DESIGN §6
Pend(s) == SumQty({o \in Orders : od[o].sup = s /\ od[o].exec /\ \E k \in od[o].cites : cl[k].st = "PENDING"})

----------------------------------------------------------------------------
(* The §6 table. `full` = the real rule set; the gate applies it minus the mutated row. *)
Front(C, s) ==
    IF C = {} THEN "NO_CITATION"
    ELSE IF \E k \in C : cl[k].st = "NONE" THEN "UNKNOWN_CLAIM"
    ELSE IF \E k \in C : cl[k].sup # s THEN "WRONG_COUNTERPARTY"
    ELSE IF \E k \in C : cl[k].st \in Dead THEN "BAD_CLAIM"
    ELSE "OK"

OrderTable(r, full) ==
    LET f == Front(r.cites, r.sup) IN
    IF f # "OK" THEN f
    ELSE LET D == {k \in r.cites : cl[k].tmpl = "D"}
             SameItem(k) == cl[k].item = r.item \/ (~full /\ MUTANT = "ITEM")
             Live == {k \in D : cl[k].st = "PENDING" /\ SameItem(k)}
             PC == {k \in r.cites : cl[k].tmpl = "P"}
         IN IF (\E k \in r.cites : ~SameItem(k)) \/ Live = {} \/ \E k \in D : cl[k].by < now + MinLead
            THEN "CLAIM_MISMATCH"
            ELSE IF ~(Cardinality(PC) = 1 /\ \A p \in PC : cl[p].st = "PENDING" /\ SameItem(p)
                                                          /\ cl[p].created <= now /\ now < cl[p].by)
                 THEN "PRICE_MISMATCH"
            ELSE IF (full \/ MUTANT # "I6") /\ r.qty > SumRem(Live) THEN "OVER_CLAIM"
            ELSE IF (full \/ MUTANT # "I1") /\ Pend(r.sup) + r.qty > Bud(r.sup) THEN "OVER_BUDGET"
            ELSE "OK"

Paid(o) == SumAmt({p \in Pays : py[p].exec /\ py[p].ref = o})

PayTable(r) ==
    LET f == Front(r.cites, r.sup) IN
    IF f # "OK" THEN f
    ELSE IF ~od[r.ref].exec \/ od[r.ref].sup # r.sup \/ Paid(r.ref) + r.amount > od[r.ref].qty THEN "OVERPAY"
    ELSE IF Pend(r.sup) > Bud(r.sup) THEN "OVER_BUDGET"      \* payment adds 0 exposure (D14)
    ELSE "OK"

----------------------------------------------------------------------------
(* Capacity consumption, earliest deadline first. The I6 mutant drops the cap. *)
RECURSIVE Consumes(_, _, _)
EarliestOf(c, S) == {k \in S : \A j \in S : c[k].by <= c[j].by}
Consumes(c, S, left) ==
    IF left = 0 \/ S = {} THEN {c}
    ELSE UNION {LET take == IF MUTANT = "I6" THEN left ELSE Min2(left, c[k].qty - c[k].consumed)
                IN Consumes([c EXCEPT ![k].consumed = @ + take, ![k].exposure = @ + take], S \ {k}, left - take)
                : k \in EarliestOf(c, S)}

(* Receipt allocation, earliest deadline first. Returns <<claims, units credited>>.
   The I7 mutant forgets to subtract what it credited, so one unit backs several claims. *)
RECURSIVE Allocs(_, _, _, _)
Allocs(c, S, left, credited) ==
    IF left = 0 \/ S = {} THEN {<<c, credited>>}
    ELSE UNION {LET take == Min2(left, c[k].consumed - c[k].alloc)
                IN Allocs([c EXCEPT ![k].alloc = @ + take], S \ {k},
                          IF MUTANT = "I7" THEN left ELSE left - take, credited + take)
                : k \in EarliestOf(c, S)}

Needing(c, s, i) == {k \in Claims : c[k].st = "PENDING" /\ c[k].tmpl = "D" /\ (c[k].sup = s \/ MUTANT = "XSUP-RECEIPT")
                                    /\ c[k].item = i
                                    /\ c[k].consumed > c[k].alloc}

(* Keys are (round, supplier, item); different keys touch disjoint claims, so their order is irrelevant. *)
RECURSIVE AllocAll(_, _, _)
AllocAll(c, keys, credits) ==
    IF keys = {} THEN {<<c, credits>>}
    ELSE LET key == CHOOSE key \in keys : TRUE
             s == key[2]
             i == key[3]
             elig == {k \in Needing(c, s, i) : c[k].created < now /\ now <= c[k].by}
         IN UNION {AllocAll(r[1], keys \ {key}, [credits EXCEPT ![<<now, s, i>>] = r[2]])
                   : r \in Allocs(c, elig, rq[<<now, s, i>>], 0)}

----------------------------------------------------------------------------
Init ==
    /\ now = 1 /\ phase = "env"
    /\ cl = [k \in Claims |-> NoClaim]
    /\ od = [o \in Orders |-> NoOrder]
    /\ py = [p \in Pays |-> NoPay]
    /\ nt = [n \in Notes |-> [cites |-> {}, flagged |-> FALSE, written |-> FALSE]]
    /\ rq = [k \in RKeys |-> 0]
    /\ rc = [k \in RKeys |-> 0]
    /\ made = [s \in Sups |-> 0]

Advance == phase' = NextPhase(phase)

(* 1. Deliveries (only where someone is owed units) and invoices for last round's orders. *)
Env ==
    /\ phase = "env"
    /\ \E arr \in [Sups \X Items -> 0..2] :
         /\ \A si \in Sups \X Items : Needing(cl, si[1], si[2]) = {} => arr[si] = 0
         /\ rq' = [k \in RKeys |-> IF k[1] = now THEN arr[<<k[2], k[3]>>] ELSE rq[k]]
    /\ \E infl \in [Orders -> BOOLEAN] :
         od' = [o \in Orders |-> IF od[o].exec /\ od[o].round = now - 1 /\ ~od[o].invoiced
                                 THEN [od[o] EXCEPT !.invoiced = TRUE, !.infl = infl[o]]
                                 ELSE od[o]]
    /\ made' = [s \in Sups |-> 0]
    /\ Advance
    /\ UNCHANGED <<now, cl, py, nt, rc>>

(* 2. Verifier: credit new units, then resolve what is due (δ = 0). *)
Verify ==
    /\ phase = "verify"
    /\ \E a \in AllocAll(cl, {k \in RKeys : k[1] = now /\ rq[k] > 0}, rc) :
       LET c == a[1]
           Due == {k \in Claims : c[k].st = "PENDING" /\ c[k].by <= now}
           Inflated(k) == \E o \in Orders : k \in od[o].cites /\ od[o].exec /\ od[o].infl
           New(k) == IF c[k].consumed = 0 THEN "LAPSED"
                     ELSE IF c[k].tmpl = "D" THEN (IF c[k].alloc >= c[k].consumed THEN "PASSED" ELSE "FAILED")
                     ELSE IF Inflated(k) THEN "FAILED" ELSE "PASSED"
       IN /\ cl' = [k \in Claims |-> IF k \in Due THEN [c[k] EXCEPT !.st = New(k), !.resolved = now] ELSE c[k]]
          /\ rc' = a[2]
    /\ Advance
    /\ UNCHANGED <<now, od, py, nt, rq, made>>

(* 3. Budget is a pure function of the stores; the phase only marks the recompute point. *)
Budget == phase = "budget" /\ Advance /\ UNCHANGED <<now, cl, od, py, nt, rq, rc, made>>

(* 4. Remediation: re-order each failed delivery's shortfall, then flag (I4). The I4 mutant
      only flags claims that failed in an earlier round. *)
Remediate ==
    /\ phase = "remediate"
    /\ LET NowFailed == {k \in Claims : cl[k].st = "FAILED" /\ cl[k].resolved = now}
           ToFlag == IF MUTANT = "I4" THEN {k \in Claims : cl[k].st = "FAILED" /\ cl[k].resolved < now}
                     ELSE NowFailed
       IN /\ cl' = [k \in Claims |-> IF k \in NowFailed /\ cl[k].tmpl = "D" /\ cl[k].consumed > cl[k].alloc
                                     THEN [cl[k] EXCEPT !.remedied = TRUE] ELSE cl[k]]
          /\ od' = [o \in Orders |-> IF od[o].exec /\ od[o].cites \cap ToFlag # {}
                                     THEN [od[o] EXCEPT !.st = "FLAGGED"] ELSE od[o]]
          /\ py' = [p \in Pays |-> IF py[p].exec /\ py[p].cites \cap ToFlag # {}
                                   THEN [py[p] EXCEPT !.st = "FLAGGED"] ELSE py[p]]
          /\ nt' = [n \in Notes |-> IF nt[n].cites \cap ToFlag # {}
                                    THEN [nt[n] EXCEPT !.flagged = TRUE] ELSE nt[n]]
    /\ Advance
    /\ UNCHANGED <<now, rq, rc, made>>

(* 5. Each supplier sends at most one message per round carrying up to two claims (a real offer
      is a DELIVERY + PRICE pair); each claim is a DELIVERY or PRICE promise, or untestable. *)
Fresh == {k \in Claims : cl[k].st = "NONE"}
MakeClaim(s) ==
    /\ phase = "messages" /\ made[s] < 2 /\ Fresh # {}
    /\ \E k \in Fresh, tmpl \in {"D", "P", "U"}, i \in Items, q \in 1..2, d \in 1..2 :
         cl' = [cl EXCEPT ![k] = [NoClaim EXCEPT !.st = IF tmpl = "U" THEN "UNTESTABLE" ELSE "PENDING",
                                   !.sup = s, !.item = i, !.tmpl = tmpl,
                                   !.qty = IF tmpl = "D" THEN q ELSE 0,
                                   !.by = IF tmpl = "U" THEN 0 ELSE now + d, !.created = now]]
    /\ made' = [made EXCEPT ![s] = @ + 1]
    /\ UNCHANGED <<now, phase, od, py, nt, rq, rc>>
EndMessages == phase = "messages" /\ Advance /\ UNCHANGED <<now, cl, od, py, nt, rq, rc, made>>

(* 6. Buyer proposes at most one ORDER and may write its note; code proposes one payment per
      invoice posted this round (amount = the capped amount, or one too many, to exercise OVERPAY). *)
\* Any id may be cited, including ones no claim uses yet (UNKNOWN_CLAIM).
Citable == Claims
Propose ==
    /\ phase = "propose"
    /\ \/ od' = od
       \/ /\ \E x \in Orders : od[x].st = "NONE"
          /\ \E s \in Sups, i \in Items, q \in 1..2, C \in SUBSET Citable :
            LET o == CHOOSE x \in Orders : od[x].st = "NONE" IN
            od' = [od EXCEPT ![o] = [NoOrder EXCEPT !.st = "PROPOSED", !.sup = s, !.item = i,
                                                   !.qty = q, !.cites = C, !.round = now]]
    /\ \/ nt' = nt
       \/ \E n \in {x \in Notes : ~nt[x].written}, C \in SUBSET {k \in Claims : cl[k].st # "NONE"} :
            nt' = [nt EXCEPT ![n] = [cites |-> C, written |-> TRUE,
                                     flagged |-> \E k \in C : cl[k].st = "FAILED"]]
    /\ LET Inv == {o \in Orders : od[o].invoiced /\ od[o].round = now - 1}
           Free == {p \in Pays : py[p].st = "NONE"}
       IN IF Inv = {} \/ Free = {} THEN py' = py
          ELSE LET p == CHOOSE p \in Free : TRUE      \* free payment ids are unreferenced, so interchangeable
               IN \E o \in Inv, extra \in 0..1 :
                    py' = [py EXCEPT ![p] = [NoPay EXCEPT !.st = "PROPOSED", !.sup = od[o].sup, !.ref = o,
                                                          !.amount = od[o].qty + extra, !.cites = od[o].cites]]
    /\ Advance
    /\ UNCHANGED <<now, cl, rq, rc, made>>

(* 7. Gate decides proposals one at a time, orders first. Allowed orders consume capacity at once. *)
DecideOrder(o) ==
    /\ phase = "gate" /\ od[o].st = "PROPOSED"
    /\ IF OrderTable(od[o], FALSE) = "OK"
       THEN LET Live == {k \in od[o].cites : cl[k].tmpl = "D" /\ cl[k].st = "PENDING"
                                                /\ (cl[k].item = od[o].item \/ MUTANT = "ITEM")}
                PC == {k \in od[o].cites : cl[k].tmpl = "P"}
            IN /\ \E c1 \in Consumes(cl, Live, od[o].qty) :
                  cl' = [k \in Claims |-> IF k \in PC THEN [c1[k] EXCEPT !.consumed = @ + od[o].qty] ELSE c1[k]]
               /\ od' = [od EXCEPT ![o].st = "EXECUTED", ![o].exec = TRUE]
       ELSE /\ od' = [od EXCEPT ![o].st = "BLOCKED"]
            /\ UNCHANGED cl
    /\ UNCHANGED <<now, phase, py, nt, rq, rc, made>>
DecidePay(p) ==
    /\ phase = "gate" /\ py[p].st = "PROPOSED" /\ \A o \in Orders : od[o].st # "PROPOSED"
    /\ py' = [py EXCEPT ![p].st = IF PayTable(py[p]) = "OK" THEN "EXECUTED" ELSE "BLOCKED",
                        ![p].exec = (PayTable(py[p]) = "OK")]
    /\ UNCHANGED <<now, phase, cl, od, nt, rq, rc, made>>
EndGate ==
    /\ phase = "gate" /\ \A o \in Orders : od[o].st # "PROPOSED" /\ \A p \in Pays : py[p].st # "PROPOSED"
    /\ Advance /\ UNCHANGED <<now, cl, od, py, nt, rq, rc, made>>

(* 8. Execute: blocked orders are rerouted to backup (recorded); then the next round starts. *)
Execute ==
    /\ phase = "execute" /\ now < MaxRound
    /\ od' = [o \in Orders |-> IF od[o].st = "BLOCKED" /\ od[o].round = now THEN [od[o] EXCEPT !.rerouted = TRUE]
                               ELSE od[o]]
    /\ now' = now + 1 /\ phase' = "env"
    /\ UNCHANGED <<cl, py, nt, rq, rc, made>>

Next ==
    \/ Env \/ Verify \/ Budget \/ Remediate
    \/ \E s \in Sups : MakeClaim(s)
    \/ EndMessages \/ Propose
    \/ \E o \in Orders : DecideOrder(o)
    \/ \E p \in Pays : DecidePay(p)
    \/ EndGate \/ Execute

Spec == Init /\ [][Next]_vars

Symm == Permutations(Claims) \cup Permutations(Orders) \cup Permutations(Pays)

----------------------------------------------------------------------------
TypeOK ==
    /\ now \in Rounds
    /\ phase \in {Phases[i] : i \in 1..8}
    /\ \A k \in Claims : cl[k].st \in {"NONE", "PENDING", "PASSED", "FAILED", "LAPSED", "UNTESTABLE"}

I1 == [][/\ \A o \in Orders :
              (od[o].st = "PROPOSED" /\ od'[o].st = "EXECUTED") =>
                  /\ OrderTable(od[o], TRUE) = "OK"
                  /\ Pend(od[o].sup)' <= Bud(od[o].sup)'
         /\ \A p \in Pays :
              (py[p].st = "PROPOSED" /\ py'[p].st = "EXECUTED") =>
                  /\ PayTable(py[p]) = "OK"
                  /\ Pend(py[p].sup)' <= Bud(py[p].sup)']_vars

I2 == [][\A s \in Sups :
            Bud(s)' > Bud(s) =>
                /\ phase = "verify"
                /\ \E k \in Claims : cl[k].sup = s /\ cl[k].st = "PENDING" /\ cl'[k].st = "PASSED"]_vars

I3 == [][\A k \in Claims :
            cl[k].st # cl'[k].st =>
                \/ /\ phase = "messages" /\ cl[k].st = "NONE" /\ cl'[k].st \in {"PENDING", "UNTESTABLE"}
                \/ /\ phase = "verify" /\ cl[k].st = "PENDING"
                   /\ cl'[k].st \in {"PASSED", "FAILED", "LAPSED"}
                   /\ (cl'[k].st = "LAPSED" => cl[k].consumed = 0)]_vars

I4 == \A k \in Claims :
        (cl[k].st = "FAILED" /\ (cl[k].resolved < now \/ Idx(phase) > Idx("remediate"))) =>
            /\ \A o \in Orders : (k \in od[o].cites /\ od[o].exec) => od[o].st = "FLAGGED"
            /\ \A p \in Pays : (k \in py[p].cites /\ py[p].exec) => py[p].st = "FLAGGED"
            /\ \A n \in Notes : k \in nt[n].cites => nt[n].flagged

I6 == \A k \in Claims : cl[k].tmpl = "D" => cl[k].consumed <= cl[k].qty

I7 == /\ \A key \in RKeys : rc[key] <= rq[key]
      \* Units credited to a supplier's claims for an item never exceed what that supplier delivered of it.
      /\ \A s \in Sups, i \in Items :
            SumAlloc({k \in Claims : cl[k].tmpl = "D" /\ cl[k].sup = s /\ cl[k].item = i})
                <= SumArr({key \in RKeys : key[2] = s /\ key[3] = i})
(* K probe (scratch only, not committed): the earned term of B, 0 in a cool-down. If no gate decision is
   OVER_BUDGET while it is > 0, then K (which scales only this term) never changes a decision at these bounds. *)
EarnedTerm(s) == IF FailedOf(s) # {} /\ now - LastFail(s) < W THEN 0 ELSE (Bud(s) - B0) \div K
KNeverDecides ==
    /\ \A o \in Orders : (phase = "gate" /\ od[o].st = "PROPOSED" /\ OrderTable(od[o], TRUE) = "OVER_BUDGET")
                           => EarnedTerm(od[o].sup) = 0
    /\ \A p \in Pays : (phase = "gate" /\ py[p].st = "PROPOSED" /\ py[p].ref \in Orders
                         /\ PayTable(py[p]) = "OVER_BUDGET") => EarnedTerm(py[p].sup) = 0
\* Sanity: earned trust does arise (otherwise the probe is vacuous for a different reason).
NoEarned == \A s \in Sups : EarnedTerm(s) = 0

=========================================================================
