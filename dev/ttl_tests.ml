module S = Tether_store.Store
let ( let* ) = Result.bind
let checked = ref 0
let require condition label = incr checked; if condition then Ok () else (prerr_endline ("FAIL TTL-UNIT " ^ label); Error S.Not_integer)
let expect expected result label = require (result = Ok expected) label
let duration = S.expire ~seconds:false
let remaining = S.ttl ~seconds:false
let all test xs = List.fold_left (fun acc x -> let* () = acc in test x) (Ok ()) xs
let run () =
  let data = [S.Str "7"; S.Str "\000\255"; S.Hash ["f", "7"]; S.List ["a"; "b"];
    S.Set ["a"; "b"]; S.ZSet ["a", "1"]; S.Stream ["id", "v"]] in
  let* () = all (fun value ->
    let base = S.put "key" value (S.put "other" (S.Str "kept") S.empty) in
    let* () = expect "-1" (remaining "key" base) "persistent sentinel" in
    let* changed, expiring = duration "key" "1500" base in
    let* () = require (changed = "1" && S.bindings expiring = S.bindings base) "expiry preserves value" in
    let* () = expect "2" (S.ttl ~seconds:true "key" expiring) "round half up" in
    let* ticked = S.advance "1001" expiring in
    let* () = expect "499" (remaining "key" ticked) "clock advances" in
    let* () = expect "0" (S.ttl ~seconds:true "key" ticked) "round down" in
    let changed, persisted = S.persist "key" ticked in
    let* () = require (changed = "1" && fst (S.persist "key" persisted) = "0") "persist result" in
    let* later = S.advance "999999" persisted in
    let* () = expect "-1" (remaining "key" later) "persist removes deadline" in
    let* boundary = S.advance "499" ticked in
    let* () = expect "0" (remaining "key" boundary) "zero lifetime at deadline" in
    let* () = require (fst (S.persist "key" boundary) = "1") "persist at deadline" in
    let* expired = S.advance "1" boundary in
    let* () = expect "-2" (remaining "key" expired) "expiry after deadline" in
    let* () = require (S.bindings expired = ["other", S.Str "kept"] && S.Keys.is_empty expired.deadlines) "expiry removes metadata" in
    all (fun amount -> let* count, after = duration "key" amount expiring in
      require (count = "1" && S.bindings after = S.bindings expired && S.Keys.is_empty after.deadlines) "immediate deletion")
      ["0"; "-1"; "-9223372036854775808"]) data in
  let base = S.put "key" (S.Str "7") S.empty in
  let* () = all (fun (ms, seconds) -> let* _, timed = duration "key" ms base in
    let* () = expect ms (remaining "key" timed) "millisecond precision" in
    expect seconds (S.ttl ~seconds:true "key" timed) "second rounding")
    ["1", "0"; "499", "0"; "500", "1"; "999", "1"; "1000", "1"; "1499", "1"; "1500", "2"] in
  let* _, timed = S.expire ~seconds:true "key" "10" base in
  let* () = expect "10000" (remaining "key" timed) "seconds scale" in
  let* () = all (fun initial ->
    let* () = require (S.expire ~seconds:true "key" "9223372036854776" initial = Error (S.Expire_range "expire")) "seconds overflow" in
    let* () = require (S.expire ~seconds:true "key" "-9223372036854776" initial = Error (S.Expire_range "expire")) "negative seconds overflow" in
    all (fun amount -> require (duration "key" amount initial = Error S.Not_integer) "invalid duration")
      ["01"; "+1"; "-0"; "1.5"; "9223372036854775808"]) [S.empty; timed] in
  let* () = expect ("0", S.empty) (duration "absent" "1" S.empty) "missing expiry" in
  let* () = require (S.persist "absent" S.empty = ("0", S.empty)) "missing persist" in
  let* advanced = S.advance "1000" timed in
  let* () = require (duration "key" "9223372036854775807" advanced = Error (S.Expire_range "pexpire")) "absolute overflow" in
  let* () = require (S.advance "-1" timed = Error S.Not_integer && S.advance "9223372036854775807" advanced = Error S.Overflow) "invalid clock" in
  let* _, large = duration "key" "9007199254740991" base in
  let* () = expect "9007199254740991" (remaining "key" large) "largest exact reply" in
  let* _, inexact = duration "key" "9007199254740993" base in
  let* () = require (remaining "key" inexact = Error S.Expire_reply) "rounded reply refused" in
  let* () = expect "9007199254741" (S.ttl ~seconds:true "key" inexact) "large seconds exact" in
  let _, replaced = S.set "key" "fresh" timed in
  let* () = expect "-1" (remaining "key" replaced) "set clears expiry" in
  let* _, incremented = S.incr "key" timed in
  let* () = expect "10000" (remaining "key" incremented) "incr preserves expiry" in
  let* () = require (S.hset "key" "f" "v" timed = Error S.Wrong_type) "error preserves state" in
  let* () = all (fun (value, edit) -> let* _, expiring = duration "key" "2000" (S.put "key" value S.empty) in
    let* after = edit expiring in expect "2000" (remaining "key" after) "mutation preserves expiry")
    [S.Hash ["f", "7"], (fun s -> Result.map snd (S.hset "key" "f" "8" s));
     S.Set ["a"], (fun s -> Result.map snd (S.sadd "key" "b" s));
     S.List ["a"; "b"], (fun s -> Result.map snd (S.ltrim "key" "0" "0" s))] in
  let sets = S.put "source" (S.Set ["a"; "b"]) (S.put "key" (S.Set ["z"]) S.empty) in
  let* _, sets = duration "source" "2000" sets in let* _, sets = duration "key" "3000" sets in
  let* _, moved = S.smove "source" "key" "a" sets in
  let* () = expect "2000" (remaining "source" moved) "move source deadline" in
  let* () = expect "3000" (remaining "key" moved) "move target deadline" in
  let* _, stored = S.sstore S.Members.union "key" "source" "key" sets in
  let* () = expect "-1" (remaining "key" stored) "set store clears expiry" in
  let* _, moved = S.smove "source" "new" "b" moved in
  let* () = expect "-2" (remaining "source" moved) "move deletes source deadline" in
  let* () = expect "-1" (remaining "new" moved) "move new target persistent" in
  let* _, refreshed = duration "key" "1" timed in
  let* expired = S.advance "2" refreshed in
  let* _, recreated = S.incr "key" expired in
  let* () = expect "-1" (remaining "key" recreated) "recreation persistent" in
  print_endline ("PASS TTL-UNIT cases=" ^ string_of_int !checked); Ok ()
let () = run () |> Result.fold ~ok:Fun.id ~error:(fun error -> prerr_endline (S.message error); exit 1)
