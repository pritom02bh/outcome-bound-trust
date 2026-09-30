------------------------------- MODULE KProbe -------------------------------
(* Non-vacuity probes for the budget growth multiplier K (DECISIONS D36a).
   Each probe is checked as an invariant that must be VIOLATED: the counterexample is the witness that the
   bounds exercise K. If a probe holds exhaustively, K can't change anything there and the config fails.
   These are not properties of OBT; run_nonvacuity.sh checks them, run_mutants.sh never does. *)
EXTENDS OBT

\* The earned term of B(s), the only part K multiplies. 0 during a cool-down, where B = B0 for every K.
EarnedTerm(s) == IF FailedOf(s) # {} /\ now - LastFail(s) < W THEN 0 ELSE (Bud(s) - B0) \div K

\* Decisions the gate is about to take (DecideOrder / DecidePay are enabled on these).
GateOrder(o) == phase = "gate" /\ od[o].st = "PROPOSED"
GatePay(p) == phase = "gate" /\ py[p].st = "PROPOSED" /\ py[p].ref \in Orders
              /\ \A o \in Orders : od[o].st # "PROPOSED"

\* Witness 1: the budget blocks something while the counterparty has earned trust.
BudgetNeverBindsWhenEarned ==
    /\ \A o \in Orders : GateOrder(o) /\ OrderTable(od[o], TRUE) = "OVER_BUDGET" => EarnedTerm(od[o].sup) = 0
    /\ \A p \in Pays : GatePay(p) /\ PayTable(py[p]) = "OVER_BUDGET" => EarnedTerm(py[p].sup) = 0

\* Witness 2: a reachable decision that K = 1 and K = 2 take differently. OVER_BUDGET is the last row of both
\* tables, so when a proposal reaches it (result OK or OVER_BUDGET) the budget comparison alone decides.
Alt == IF K = 1 THEN 2 ELSE 1
BudAt(s, k) == B0 + k * EarnedTerm(s)
OrderFits(o, k) == Pend(od[o].sup) + od[o].qty <= BudAt(od[o].sup, k)
PayFits(p, k) == Pend(py[p].sup) <= BudAt(py[p].sup, k)
KNeverChangesADecision ==
    /\ \A o \in Orders : GateOrder(o) /\ OrderTable(od[o], TRUE) \in {"OK", "OVER_BUDGET"}
                            => (OrderFits(o, K) <=> OrderFits(o, Alt))
    /\ \A p \in Pays : GatePay(p) /\ PayTable(py[p]) \in {"OK", "OVER_BUDGET"}
                          => (PayFits(p, K) <=> PayFits(p, Alt))
=============================================================================
