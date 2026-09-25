-------------------------------- MODULE OBT --------------------------------
(* Outcome-Bound Trust: gate, budget, verifier and dependency tracker for one
   counterparty (DESIGN §6-7). Oracle outcomes are nondeterministic, so every
   pass/fail pattern is explored. Claims start in the offer book (DECISIONS D4)
   and are committed to the ledger when an allowed action cites them.

   I1 gate safety, I2 earned trust and I3 ledger integrity are action
   properties (they talk about the step that executes / raises B / resolves).
   I4 propagation is a state invariant, so it must already hold right after
   the verifier step that failed the claim.

   CHECK_BUDGET = FALSE is the mutated gate with the budget test removed. *)
EXTENDS Naturals, FiniteSets

CONSTANTS Claims, Actions, Notes, Values, B0, W, MaxRound, CHECK_BUDGET

VARIABLES
    cstatus,   \* NONE | OFFER | OFFER_U | PENDING | PASSED | FAILED
    exposure,  \* realized exposure per claim
    resolved,  \* round a claim was resolved (0 = never)
    astatus,   \* NONE | EXECUTED | BLOCKED | FLAGGED
    aexec,     \* was the action executed (kept once FLAGGED)
    acites, avalue,
    ncites, nflag,
    now,
    step       \* name of the last step, so properties can say "only the verifier"

vars == <<cstatus, exposure, resolved, astatus, aexec, acites, avalue, ncites, nflag, now, step>>

Ledger == {"PENDING", "PASSED", "FAILED"}

RECURSIVE SumVal(_)
SumVal(S) == IF S = {} THEN 0
             ELSE LET a == CHOOSE x \in S : TRUE IN avalue[a] + SumVal(S \ {a})

MaxOf(S) == IF S = {} THEN 0 ELSE CHOOSE m \in S : \A y \in S : y <= m

Failed == {k \in Claims : cstatus[k] = "FAILED"}
LastFail == MaxOf({resolved[k] : k \in Failed})

\* B(c) with the cool-down rule of DECISIONS D3.
Bud ==
    IF Failed # {} /\ now - LastFail < W THEN B0
    ELSE LET floor == IF Failed = {} THEN 0 ELSE LastFail + W
             earned == {exposure[k] : k \in {j \in Claims : cstatus[j] = "PASSED" /\ resolved[j] >= floor}}
         IN B0 + MaxOf(earned)

\* P(c): executed actions citing at least one PENDING claim, each counted once.
Pend == SumVal({a \in Actions : aexec[a] /\ \E k \in acites[a] : cstatus[k] = "PENDING"})

Citable(k) == cstatus[k] \in {"OFFER", "PENDING", "PASSED"}

Allow(S, v) ==
    /\ S # {}
    /\ \A k \in S : cstatus[k] # "NONE"          \* UNKNOWN_CLAIM
    /\ \A k \in S : Citable(k)                    \* BAD_CLAIM (FAILED or untestable)
    /\ (CHECK_BUDGET => Pend + v <= Bud)          \* OVER_BUDGET

Init ==
    /\ cstatus = [k \in Claims |-> "NONE"]
    /\ exposure = [k \in Claims |-> 0]
    /\ resolved = [k \in Claims |-> 0]
    /\ astatus = [a \in Actions |-> "NONE"]
    /\ aexec = [a \in Actions |-> FALSE]
    /\ acites = [a \in Actions |-> {}]
    /\ avalue = [a \in Actions |-> 0]
    /\ ncites = [n \in Notes |-> {}]
    /\ nflag = [n \in Notes |-> FALSE]
    /\ now = 1
    /\ step = "init"

\* Extractor output lands in the offer book: testable or not.
Offer(k) ==
    /\ cstatus[k] = "NONE"
    /\ \E s \in {"OFFER", "OFFER_U"} : cstatus' = [cstatus EXCEPT ![k] = s]
    /\ step' = "offer"
    /\ UNCHANGED <<exposure, resolved, astatus, aexec, acites, avalue, ncites, nflag, now>>

\* Buyer proposes; the gate decides in the same step.
Propose(a, S, v) ==
    /\ astatus[a] = "NONE"
    /\ acites' = [acites EXCEPT ![a] = S]
    /\ avalue' = [avalue EXCEPT ![a] = v]
    /\ IF Allow(S, v)
       THEN LET committed == [k \in Claims |-> IF k \in S /\ cstatus[k] = "OFFER" THEN "PENDING" ELSE cstatus[k]]
            IN /\ cstatus' = committed
               /\ exposure' = [k \in Claims |->
                                 IF k \in S /\ committed[k] = "PENDING" THEN exposure[k] + v ELSE exposure[k]]
               /\ astatus' = [astatus EXCEPT ![a] = "EXECUTED"]
               /\ aexec' = [aexec EXCEPT ![a] = TRUE]
       ELSE /\ astatus' = [astatus EXCEPT ![a] = "BLOCKED"]
            /\ UNCHANGED <<cstatus, exposure, aexec>>
    /\ step' = "gate"
    /\ UNCHANGED <<resolved, ncites, nflag, now>>

\* Verifier resolves a PENDING claim; the dependency tracker flags in the same step.
Verify(k) ==
    /\ cstatus[k] = "PENDING"
    /\ \E out \in {"PASSED", "FAILED"} :
         /\ cstatus' = [cstatus EXCEPT ![k] = out]
         /\ IF out = "FAILED"
            THEN /\ astatus' = [a \in Actions |->
                                 IF k \in acites[a] /\ astatus[a] = "EXECUTED" THEN "FLAGGED" ELSE astatus[a]]
                 /\ nflag' = [n \in Notes |-> nflag[n] \/ k \in ncites[n]]
            ELSE UNCHANGED <<astatus, nflag>>
    /\ resolved' = [resolved EXCEPT ![k] = now]
    /\ step' = "verify"
    /\ UNCHANGED <<exposure, aexec, acites, avalue, ncites, now>>

\* Agent writes a note citing claims; flagged on entry if one already FAILED.
AddNote(n, S) ==
    /\ ncites[n] = {} /\ ~nflag[n]
    /\ S # {}
    /\ ncites' = [ncites EXCEPT ![n] = S]
    /\ nflag' = [nflag EXCEPT ![n] = \E k \in S : cstatus[k] = "FAILED"]
    /\ step' = "note"
    /\ UNCHANGED <<cstatus, exposure, resolved, astatus, aexec, acites, avalue, now>>

Tick ==
    /\ now < MaxRound
    /\ now' = now + 1
    /\ step' = "tick"
    /\ UNCHANGED <<cstatus, exposure, resolved, astatus, aexec, acites, avalue, ncites, nflag>>

Next ==
    \/ \E k \in Claims : Offer(k) \/ Verify(k)
    \/ \E a \in Actions, S \in SUBSET Claims, v \in Values : Propose(a, S, v)
    \/ \E n \in Notes, S \in SUBSET Claims : AddNote(n, S)
    \/ Tick

Spec == Init /\ [][Next]_vars

TypeOK ==
    /\ cstatus \in [Claims -> {"NONE", "OFFER", "OFFER_U", "PENDING", "PASSED", "FAILED"}]
    /\ astatus \in [Actions -> {"NONE", "EXECUTED", "BLOCKED", "FLAGGED"}]
    /\ now \in 1..MaxRound

-----------------------------------------------------------------------------
(* I1 Gate safety: at the step an action becomes EXECUTED, it cites >= 1 claim,
   none FAILED or untestable, and P <= B afterwards. *)
I1 == [][\A a \in Actions :
            (astatus[a] = "NONE" /\ astatus'[a] = "EXECUTED") =>
                /\ acites'[a] # {}
                /\ \A k \in acites'[a] : cstatus'[k] \in {"PENDING", "PASSED"}
                /\ Pend' <= Bud']_vars

(* I2 Earned trust: B rises only in a verifier step that sets a claim to PASSED. *)
I2 == [][Bud' > Bud =>
            /\ step' = "verify"
            /\ \E k \in Claims : cstatus[k] = "PENDING" /\ cstatus'[k] = "PASSED"]_vars

(* I3 Ledger integrity: once in the ledger, status only moves PENDING -> PASSED | FAILED,
   and only in a verifier step. Ledger claims never leave the ledger. *)
I3 == [][\A k \in Claims :
            /\ cstatus[k] \in Ledger => cstatus'[k] \in Ledger
            /\ (cstatus[k] # cstatus'[k] /\ cstatus[k] \in Ledger) =>
                   /\ cstatus[k] = "PENDING" /\ cstatus'[k] \in {"PASSED", "FAILED"}
                   /\ step' = "verify"
            /\ cstatus'[k] \in {"PASSED", "FAILED"} /\ cstatus[k] # cstatus'[k] => cstatus[k] = "PENDING"]_vars

(* I4 Propagation: as a state invariant, it holds right after the failing step. *)
I4 == \A k \in Failed :
        /\ \A a \in Actions : (k \in acites[a] /\ aexec[a]) => astatus[a] = "FLAGGED"
        /\ \A n \in Notes : k \in ncites[n] => nflag[n]
=============================================================================
