------------------------------- MODULE MCsim -------------------------------
(* Random simulation of OBT at full bounds (spec/run_simulation.sh). Adds only
   bookkeeping, as an always-true invariant; OBT itself is unchanged.

   TLC 2.19 reports no trace statistics in simulation mode, so:
   - the trace count is fixed with -simulate num=N (every trace here runs to the
     final round's execute phase, where the spec deadlocks, well under -depth);
   - the deepest trace is recorded here: a state in the final execute phase is
     the end of a trace, and each new maximum of its level is printed. *)
EXTENDS OBT, TLC

ASSUME TLCSet(2, 0)
Final == phase = "execute" /\ now = MaxRound
SimDepth ==
    Final => IF TLCGet("level") > TLCGet(2)
             THEN TLCSet(2, TLCGet("level")) /\ PrintT(<<"SIMDEPTH", TLCGet("level")>>)
             ELSE TRUE
\* Guided variant (SPECIFICATION GuidedSpec, replay sample only). Guided: new ORDER proposals cite only PENDING claims
\* of the order's own supplier and item, including at least one DELIVERY and one PRICE claim (lead time, price
\* validity, capacity and budget are left to chance). It removes behaviors,
\* never adds any, so it biases random traces toward the gate's allow / capacity / budget / payment rows
\* that uniform citations almost never reach.
Guided ==
    \A o \in Orders :
        (od[o].st = "NONE" /\ od'[o].st = "PROPOSED") =>
            /\ \A k \in od'[o].cites : cl[k].st = "PENDING" /\ cl[k].sup = od'[o].sup /\ cl[k].item = od'[o].item
            /\ \E k \in od'[o].cites : cl[k].tmpl = "D"
            /\ \E k \in od'[o].cites : cl[k].tmpl = "P"
\* Suppliers send real offers: no untestable claims, and a supplier's second claim in a round completes
\* a DELIVERY + PRICE pair for the item of its first. Without this, 89% of guided traces never hold a
\* citable pair (the 3-id claim pool is spent on unmatched claims) and never propose an order.
GuidedClaims ==
    \A k \in Claims :
        (cl[k].st = "NONE" /\ cl'[k].st # "NONE") =>
            /\ cl'[k].tmpl # "U"
            /\ \A j \in Claims : (cl[j].st # "NONE" /\ cl[j].sup = cl'[k].sup /\ cl[j].created = now) =>
                                   (cl[j].item = cl'[k].item /\ cl[j].tmpl # cl'[k].tmpl)
\* A conjunct of the next-state relation, not an ACTION_CONSTRAINT: TLC's simulator ends a trace at a
\* constraint-violating step instead of drawing another successor.
GuidedSpec == Init /\ [][Next /\ Guided /\ GuidedClaims]_vars
=============================================================================
