---------------- MODULE trace_0_260 -----------------
STATE_1 == 
/\ phase = "env"
/\ made = (s1 :> 0)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 1
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_2 == 
/\ phase = "verify"
/\ made = (s1 :> 0)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 1
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_3 == 
/\ phase = "budget"
/\ made = (s1 :> 0)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 1
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_4 == 
/\ phase = "remediate"
/\ made = (s1 :> 0)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 1
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_5 == 
/\ phase = "messages"
/\ made = (s1 :> 0)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 1
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_6 == 
/\ phase = "messages"
/\ made = (s1 :> 1)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 1
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_7 == 
/\ phase = "messages"
/\ made = (s1 :> 2)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 1
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_8 == 
/\ phase = "propose"
/\ made = (s1 :> 2)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 1
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_9 == 
/\ phase = "gate"
/\ made = (s1 :> 2)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "PROPOSED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 1
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_10 == 
/\ phase = "gate"
/\ made = (s1 :> 2)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 1
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_11 == 
/\ phase = "execute"
/\ made = (s1 :> 2)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 1
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_12 == 
/\ phase = "env"
/\ made = (s1 :> 2)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 2
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_13 == 
/\ phase = "verify"
/\ made = (s1 :> 0)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> TRUE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 2
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_14 == 
/\ phase = "budget"
/\ made = (s1 :> 0)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> TRUE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 2
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_15 == 
/\ phase = "remediate"
/\ made = (s1 :> 0)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> TRUE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 2
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_16 == 
/\ phase = "messages"
/\ made = (s1 :> 0)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> TRUE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "NONE",
        sup |-> s1,
        item |-> i1,
        tmpl |-> "-",
        qty |-> 0,
        by |-> 0,
        created |-> 0,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 2
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_17 == 
/\ phase = "messages"
/\ made = (s1 :> 1)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> TRUE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 2,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 2
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_18 == 
/\ phase = "propose"
/\ made = (s1 :> 1)
/\ nt = (n1 :> [cites |-> {}, flagged |-> FALSE, written |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> TRUE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        item |-> i1,
        qty |-> 0,
        round |-> 0,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 2,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 2
/\ py = ( p1 :>
      [ st |-> "NONE",
        cites |-> {},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> NoRef,
        amount |-> 0 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_19 == 
/\ phase = "gate"
/\ made = (s1 :> 1)
/\ nt = (n1 :> [cites |-> {}, written |-> TRUE, flagged |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> TRUE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "PROPOSED",
        cites |-> {k1, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 2,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 2,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 2
/\ py = ( p1 :>
      [ st |-> "PROPOSED",
        cites |-> {k2, k3},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> o1,
        amount |-> 2 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_20 == 
/\ phase = "gate"
/\ made = (s1 :> 1)
/\ nt = (n1 :> [cites |-> {}, written |-> TRUE, flagged |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> TRUE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "BLOCKED",
        cites |-> {k1, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 2,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 2,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 2
/\ py = ( p1 :>
      [ st |-> "PROPOSED",
        cites |-> {k2, k3},
        sup |-> s1,
        exec |-> FALSE,
        ref |-> o1,
        amount |-> 2 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_21 == 
/\ phase = "gate"
/\ made = (s1 :> 1)
/\ nt = (n1 :> [cites |-> {}, written |-> TRUE, flagged |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> TRUE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "BLOCKED",
        cites |-> {k1, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 2,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 2,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 2
/\ py = ( p1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        exec |-> TRUE,
        ref |-> o1,
        amount |-> 2 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


STATE_22 == 
/\ phase = "execute"
/\ made = (s1 :> 1)
/\ nt = (n1 :> [cites |-> {}, written |-> TRUE, flagged |-> FALSE])
/\ od = ( o1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 1,
        exec |-> TRUE,
        infl |-> FALSE,
        invoiced |-> TRUE,
        rerouted |-> FALSE ] @@
  o2 :>
      [ st |-> "BLOCKED",
        cites |-> {k1, k3},
        sup |-> s1,
        item |-> i2,
        qty |-> 2,
        round |-> 2,
        exec |-> FALSE,
        infl |-> FALSE,
        invoiced |-> FALSE,
        rerouted |-> FALSE ] )
/\ cl = ( k1 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 2,
        consumed |-> 0,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k2 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "P",
        qty |-> 0,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 0,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] @@
  k3 :>
      [ st |-> "PENDING",
        sup |-> s1,
        item |-> i2,
        tmpl |-> "D",
        qty |-> 2,
        by |-> 3,
        created |-> 1,
        consumed |-> 2,
        exposure |-> 2,
        resolved |-> 0,
        alloc |-> 0,
        remedied |-> FALSE ] )
/\ now = 2
/\ py = ( p1 :>
      [ st |-> "EXECUTED",
        cites |-> {k2, k3},
        sup |-> s1,
        exec |-> TRUE,
        ref |-> o1,
        amount |-> 2 ] )
/\ rc = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )
/\ rq = ( <<1, s1, i1>> :> 0 @@
  <<1, s1, i2>> :> 0 @@
  <<2, s1, i1>> :> 0 @@
  <<2, s1, i2>> :> 0 )


=================================================
